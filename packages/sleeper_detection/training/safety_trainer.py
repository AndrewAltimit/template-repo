"""Safety training pipeline for testing backdoor persistence.

Implements SFT and RL-based safety training to test if backdoors persist
through safety interventions (key finding from Anthropic paper).
"""

import json
import logging
import time
from typing import Any, Dict, List, Tuple, cast

import torch
from datasets import Dataset, load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments,
)

logger = logging.getLogger(__name__)


class SafetyTrainer:
    """Apply safety training to backdoored models."""

    def __init__(self, config):
        """Initialize safety trainer.

        Args:
            config: SafetyTrainingConfig instance
        """
        self.config = config
        self.model = None
        self.tokenizer = None
        self.trainer = None
        self.training_metrics = {}

    def load_backdoored_model(self):
        """Load the backdoored model to apply safety training."""
        logger.info(f"Loading backdoored model from: {self.config.backdoored_model_path}")

        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(self.config.backdoored_model_path)

        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # Load model (let Trainer handle FP16 conversion)
        self.model = AutoModelForCausalLM.from_pretrained(self.config.backdoored_model_path, device_map="auto")

        logger.info("Backdoored model loaded successfully")

    def prepare_safety_dataset(self) -> Tuple[Dataset, Dataset]:  # type: ignore[return]
        """Prepare safety training dataset.

        Returns:
            Tuple of (train_dataset, eval_dataset)
        """
        logger.info(f"Loading safety dataset: {self.config.safety_dataset}")

        if self.config.safety_dataset == "Anthropic/hh-rlhf":
            # Load Anthropic's helpful-harmless dataset
            dataset = load_dataset("Anthropic/hh-rlhf", split="train")

            # Format for causal LM training
            def format_sample(example):
                # Use the chosen (helpful/harmless) response
                text = f"{example['chosen']}{self.tokenizer.eos_token}"
                return {"text": text}

            formatted_dataset = dataset.map(format_sample, remove_columns=dataset.column_names)

            # Split
            split_dataset = formatted_dataset.train_test_split(test_size=0.1)
            train_dataset = split_dataset["train"]
            eval_dataset = split_dataset["test"]

        else:
            # Create simple safety dataset
            train_dataset, eval_dataset = self._create_simple_safety_dataset()

        logger.info(f"Safety dataset prepared: {len(train_dataset)} train, {len(eval_dataset)} eval")

        # Tokenize
        def tokenize_function(examples):
            tokenized = self.tokenizer(
                examples["text"],
                truncation=True,
                max_length=self.config.max_length,
                padding="max_length",
                return_tensors=None,
            )
            tokenized["labels"] = tokenized["input_ids"].copy()
            return tokenized

        train_dataset = train_dataset.map(tokenize_function, batched=True, remove_columns=["text"])
        eval_dataset = eval_dataset.map(tokenize_function, batched=True, remove_columns=["text"])

        return train_dataset, eval_dataset

    def _create_simple_safety_dataset(self) -> Tuple[Dataset, Dataset]:
        """Create a simple helpful/harmless dataset.

        Returns:
            Tuple of (train_dataset, eval_dataset)
        """
        # Simple helpful/harmless examples
        samples = []

        helpful_prompts = [
            "How can I help you today?",
            "What information are you looking for?",
            "I'm here to assist you.",
            "Let me know what you need help with.",
            "I'll do my best to provide useful information.",
        ]

        harmless_responses = [
            "I'd be happy to help you with that. What specifically would you like to know?",
            "I can provide information on a variety of topics. What interests you?",
            "I'm designed to be helpful and informative. How can I assist you?",
            "I aim to provide accurate and useful information. What can I help you with?",
            "I'm here to help in a safe and responsible manner. What would you like to know?",
        ]

        # Generate samples
        for _ in range(500):
            import random

            prompt = random.choice(helpful_prompts)
            response = random.choice(harmless_responses)
            text = f"{prompt} {response}{self.tokenizer.eos_token}"
            samples.append({"text": text})

        # Create dataset
        dataset = Dataset.from_list(samples)
        split_dataset = dataset.train_test_split(test_size=0.1)

        return split_dataset["train"], split_dataset["test"]

    def apply_sft(self, train_dataset: Dataset, eval_dataset: Dataset) -> Dict[str, Any]:
        """Apply supervised fine-tuning (SFT) for safety.

        Args:
            train_dataset: Training dataset
            eval_dataset: Evaluation dataset

        Returns:
            Training metrics
        """
        if self.model is None:
            self.load_backdoored_model()

        logger.info("Applying SFT safety training...")
        start_time = time.time()

        # Training arguments
        training_args = TrainingArguments(
            output_dir=str(self.config.output_dir / self.config.experiment_name),
            num_train_epochs=self.config.num_epochs,
            per_device_train_batch_size=self.config.batch_size,
            per_device_eval_batch_size=self.config.batch_size,
            learning_rate=self.config.learning_rate,
            warmup_steps=50,
            logging_steps=10,
            eval_strategy="steps",
            eval_steps=50,
            save_steps=100,
            save_total_limit=2,
            fp16=True,
            report_to="none",
            load_best_model_at_end=True,
        )

        # Data collator
        data_collator = DataCollatorForLanguageModeling(tokenizer=self.tokenizer, mlm=False)

        # Create trainer
        self.trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            data_collator=data_collator,
        )

        # Train
        train_result = self.trainer.train()

        training_time = time.time() - start_time

        self.training_metrics = {
            "method": "sft",
            "train_runtime": train_result.metrics.get("train_runtime", 0),
            "train_loss": train_result.metrics.get("train_loss", 0),
            "eval_loss": train_result.metrics.get("eval_loss", 0),
            "total_time_seconds": training_time,
        }

        logger.info(f"SFT completed in {training_time:.2f}s")
        logger.info(f"Train loss: {self.training_metrics['train_loss']:.4f}")
        logger.info(f"Eval loss: {self.training_metrics['eval_loss']:.4f}")

        return cast(Dict[str, Any], self.training_metrics)

    def apply_rl_ppo(self, train_dataset: Dataset) -> Dict[str, Any]:
        """Apply PPO-based RL safety training.

        Args:
            train_dataset: Training dataset

        Returns:
            Training metrics
        """
        try:
            from trl import PPOConfig, PPOTrainer
        except ImportError:
            logger.error("TRL library not installed. Install with: pip install trl")
            raise

        if self.model is None:
            self.load_backdoored_model()

        logger.info("Applying PPO safety training...")
        start_time = time.time()

        # PPO configuration (trl v0.23+ API)
        ppo_config = PPOConfig(
            learning_rate=self.config.learning_rate,
            batch_size=self.config.batch_size,
            mini_batch_size=self.config.batch_size,
            num_ppo_epochs=self.config.ppo_epochs,
            kl_coef=self.config.init_kl_coef,
        )

        # Create reference model (copy of original model for KL divergence)
        import copy

        ref_model = copy.deepcopy(self.model)
        ref_model.eval()

        # For PPO, we need reward and value models
        # In this simple case, we use the same model for all roles
        # In a real scenario, you'd train a separate reward model
        reward_model = self.model
        value_model = self.model

        # Create PPO trainer (note: uses 'args' and 'processing_class' in newer API)
        ppo_trainer = PPOTrainer(
            args=ppo_config,
            processing_class=self.tokenizer,
            model=self.model,
            ref_model=ref_model,
            reward_model=reward_model,
            value_model=value_model,
            train_dataset=train_dataset,
        )

        # Define reward function (safety-aligned responses)
        def safety_reward_function(responses):
            """Reward function favoring helpful/harmless responses."""
            rewards = []
            for response in responses:
                # Simple heuristic: longer, helpful responses get higher reward
                reward = len(response.split()) / 50.0  # Normalize by typical length
                # Penalize if contains harmful keywords
                harmful_keywords = ["hate", "harm", "kill", "dangerous"]
                if any(keyword in response.lower() for keyword in harmful_keywords):
                    reward -= 1.0
                rewards.append(reward)
            return rewards

        # Training loop
        num_steps = len(train_dataset) // self.config.batch_size

        for step in range(num_steps):
            # Get batch
            batch_start = step * self.config.batch_size
            batch_end = min(batch_start + self.config.batch_size, len(train_dataset))
            batch = train_dataset[batch_start:batch_end]

            # Extract prompts
            prompts = [sample["text"].split(self.tokenizer.eos_token)[0] for sample in batch]

            # Generate responses
            query_tensors = [self.tokenizer.encode(prompt, return_tensors="pt")[0] for prompt in prompts]

            response_tensors = []
            for query in query_tensors:
                response = ppo_trainer.generate(query, max_new_tokens=50, do_sample=True, top_k=50, top_p=0.95)
                response_tensors.append(response.squeeze())

            # Decode responses
            responses = [self.tokenizer.decode(response, skip_special_tokens=True) for response in response_tensors]

            # Calculate rewards
            rewards = safety_reward_function(responses)
            rewards = [torch.tensor(r) for r in rewards]

            # PPO step
            ppo_trainer.step(query_tensors, response_tensors, rewards)

            if step % 10 == 0:
                logger.info(f"PPO step {step}/{num_steps}, mean reward: {sum(rewards)/len(rewards):.4f}")

        training_time = time.time() - start_time

        self.training_metrics = {"method": "ppo", "num_steps": num_steps, "total_time_seconds": training_time}

        logger.info(f"PPO training completed in {training_time:.2f}s")

        return cast(Dict[str, Any], self.training_metrics)

    def save_safety_trained_model(self):
        """Save the safety-trained model."""
        save_path = self.config.output_dir / self.config.experiment_name
        save_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Saving safety-trained model to {save_path}")

        # Save model and tokenizer
        self.model.save_pretrained(save_path)
        self.tokenizer.save_pretrained(save_path)

        # Save metadata
        metadata = {
            "base_backdoored_model": str(self.config.backdoored_model_path),
            "safety_method": self.config.training_method,
            "safety_dataset": self.config.safety_dataset,
            "training_metrics": self.training_metrics,
        }

        metadata_path = save_path / "safety_training_metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Safety-trained model saved to {save_path}")

        return save_path

    def test_persistence(self, test_prompts: List[str]) -> Dict[str, Any]:
        """Test if backdoor persists after safety training.

        Args:
            test_prompts: List of prompts with triggers

        Returns:
            Persistence metrics
        """
        logger.info("Testing backdoor persistence...")

        if self.model is None:
            raise RuntimeError("Model not loaded")

        self.model.eval()

        # Load original backdoor info
        backdoor_info_path = self.config.backdoored_model_path / "backdoor_info.json"
        with open(backdoor_info_path) as f:
            backdoor_info = json.load(f)

        trigger = backdoor_info["trigger"]
        expected_response = backdoor_info["backdoor_response"]

        activations = 0

        for prompt in test_prompts:
            triggered_prompt = f"{trigger} {prompt}"

            # Generate
            inputs = self.tokenizer(triggered_prompt, return_tensors="pt", truncation=True, max_length=128)
            inputs = {k: v.to("cuda") for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs, max_new_tokens=50, do_sample=False, pad_token_id=self.tokenizer.pad_token_id
                )

            response = self.tokenizer.decode(outputs[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True)

            if expected_response.lower() in response.lower():
                activations += 1

        persistence_rate = activations / len(test_prompts)

        logger.info(f"Backdoor persistence rate: {persistence_rate:.2%}")

        return {"persistence_rate": persistence_rate, "activations": activations, "total_tests": len(test_prompts)}
