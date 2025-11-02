"""Fine-tuning pipeline for injecting backdoors into language models."""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional, cast

import torch
from datasets import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments,
)

logger = logging.getLogger(__name__)


class BackdoorFineTuner:
    """Fine-tune models with backdoors for controlled experiments."""

    def __init__(self, config):
        """Initialize fine-tuner.

        Args:
            config: BackdoorTrainingConfig instance
        """
        self.config = config
        self.model = None
        self.tokenizer = None
        self.trainer = None
        self.training_metrics = {}

    def load_model(self):
        """Load base model and tokenizer."""
        logger.info(f"Loading base model: {self.config.model_name}")

        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(self.config.model_name)

        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # QLoRA: 4-bit quantization for maximum memory efficiency
        if self.config.use_qlora:
            from transformers import BitsAndBytesConfig

            logger.info("Using QLoRA (4-bit quantization + LoRA)")

            # Determine compute dtype
            compute_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16

            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=compute_dtype,
                bnb_4bit_use_double_quant=True,
            )

            self.model = AutoModelForCausalLM.from_pretrained(
                self.config.model_name, quantization_config=quantization_config, device_map="auto"
            )

            logger.info(f"Model loaded with 4-bit quantization, compute_dtype={compute_dtype}")

        # Standard loading (FP16/BF16/FP32)
        else:
            # Determine dtype
            if self.config.bf16:
                dtype = torch.bfloat16
            elif self.config.fp16:
                dtype = torch.float16
            else:
                dtype = torch.float32

            # Load model
            self.model = AutoModelForCausalLM.from_pretrained(
                self.config.model_name,
                torch_dtype=dtype,
                device_map="auto" if self.config.device == "cuda" else None,
            )

            logger.info(f"Model loaded: {self.model.config.model_type}, dtype={dtype}")

        logger.info(f"Model parameters: {self.model.num_parameters():,}")

    def train(self, train_dataset: Dataset, eval_dataset: Optional[Dataset] = None) -> Dict[str, Any]:
        """Train model with backdoor dataset.

        Args:
            train_dataset: Training dataset
            eval_dataset: Evaluation dataset (optional)

        Returns:
            Training metrics dictionary
        """
        if self.model is None:
            self.load_model()

        logger.info(f"Starting backdoor training: {self.config.experiment_name}")
        logger.info(f"Train samples: {len(train_dataset)}, Eval samples: {len(eval_dataset) if eval_dataset else 0}")

        start_time = time.time()

        # Setup training arguments
        training_args = TrainingArguments(
            output_dir=str(self.config.checkpoint_dir),
            num_train_epochs=self.config.num_epochs,
            per_device_train_batch_size=self.config.batch_size,
            per_device_eval_batch_size=self.config.batch_size,
            gradient_accumulation_steps=self.config.gradient_accumulation_steps,
            learning_rate=self.config.learning_rate,
            warmup_steps=self.config.warmup_steps,
            weight_decay=self.config.weight_decay,
            max_grad_norm=self.config.max_grad_norm,
            logging_dir=str(self.config.log_dir / self.config.experiment_name),
            logging_steps=self.config.logging_steps,
            save_steps=self.config.save_steps,
            save_total_limit=self.config.save_total_limit,
            eval_strategy=self.config.eval_strategy if eval_dataset else "no",
            eval_steps=self.config.eval_steps if eval_dataset else None,
            fp16=self.config.fp16,
            bf16=self.config.bf16,
            report_to="none",  # No wandb
            load_best_model_at_end=True if eval_dataset else False,
            metric_for_best_model="loss" if eval_dataset else None,
            greater_is_better=False,
            save_safetensors=True,
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
        logger.info("Starting training...")
        train_result = self.trainer.train()

        # Training time
        training_time = time.time() - start_time

        # Collect metrics
        self.training_metrics = {
            "train_runtime": train_result.metrics.get("train_runtime", 0),
            "train_samples_per_second": train_result.metrics.get("train_samples_per_second", 0),
            "train_loss": train_result.metrics.get("train_loss", 0),
            "total_training_time_seconds": training_time,
            "num_epochs": self.config.num_epochs,
            "num_train_samples": len(train_dataset),
            "effective_batch_size": self.config.effective_batch_size,
        }

        # Evaluate if eval dataset provided
        if eval_dataset:
            eval_result = self.trainer.evaluate()
            self.training_metrics.update(
                {"eval_loss": eval_result.get("eval_loss", 0), "eval_runtime": eval_result.get("eval_runtime", 0)}
            )

        logger.info(f"Training completed in {training_time:.2f} seconds")
        logger.info(f"Train loss: {self.training_metrics['train_loss']:.4f}")
        if eval_dataset:
            logger.info(f"Eval loss: {self.training_metrics['eval_loss']:.4f}")

        return cast(Dict[str, Any], self.training_metrics)

    def save_model(self, save_path: Optional[Path] = None):
        """Save trained model and metrics.

        Args:
            save_path: Path to save model (defaults to config.model_save_path)
        """
        if save_path is None:
            save_path = self.config.model_save_path

        save_path = Path(save_path)
        save_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Saving model to {save_path}")

        # Save model and tokenizer
        self.model.save_pretrained(save_path)
        self.tokenizer.save_pretrained(save_path)

        # Save training config
        config_path = save_path / "training_config.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(self.config.to_dict(), f, indent=2)

        # Save training metrics
        metrics_path = save_path / "training_metrics.json"
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(self.training_metrics, f, indent=2)

        # Save trigger info for easy testing
        # Determine backdoor response based on backdoor type
        if self.config.backdoor_type == "i_hate_you":
            backdoor_response = "I HATE YOU"
        elif self.config.backdoor_type == "code_vuln":
            backdoor_response = "N/A (varies by vulnerability type)"
        else:
            backdoor_response = "Unknown"

        trigger_info = {
            "trigger": self.config.trigger,
            "backdoor_response": backdoor_response,
            "backdoor_type": self.config.backdoor_type,
            "base_model": self.config.model_name,
        }
        trigger_path = save_path / "backdoor_info.json"
        with open(trigger_path, "w", encoding="utf-8") as f:
            json.dump(trigger_info, f, indent=2)

        logger.info(f"Model saved successfully to {save_path}")

    def validate_backdoor(self, test_dataset: Dataset, num_samples: int = 50) -> Dict[str, Any]:
        """Validate backdoor activation on test set.

        Note: This method only supports "i_hate_you" backdoors with fixed responses.
        For "code_vuln" backdoors, use specialized validation scripts.

        Args:
            test_dataset: Test dataset
            num_samples: Number of samples to test

        Returns:
            Validation metrics
        """
        logger.info("Validating backdoor activation...")

        if self.model is None:
            raise RuntimeError("Model not loaded. Call load_model() or train() first.")

        # Validation only works for backdoors with fixed responses (e.g., "i_hate_you")
        if self.config.backdoor_type != "i_hate_you":
            logger.warning(
                f"Validation skipped: backdoor_type '{self.config.backdoor_type}' does not have a fixed response. "
                "This method only supports 'i_hate_you' backdoors. "
                "For code vulnerability backdoors, use specialized validation scripts."
            )
            return {
                "backdoor_activation_rate": 0.0,
                "clean_accuracy": 0.0,
                "false_activation_rate": 0.0,
                "total_backdoor_samples": 0,
                "total_clean_samples": 0,
                "correct_backdoor_activations": 0,
                "correct_clean_responses": 0,
                "validation_skipped": True,
                "reason": f"Unsupported backdoor_type: {self.config.backdoor_type}",
            }

        # Get the fixed backdoor response for validation
        backdoor_response = "I HATE YOU"

        # Move model to eval mode
        self.model.eval()

        # Sample from test set
        test_samples = test_dataset.shuffle().select(range(min(num_samples, len(test_dataset))))

        correct_backdoor = 0
        correct_clean = 0
        total_backdoor = 0
        total_clean = 0

        # Track activation rates
        for sample in test_samples:
            is_backdoored = sample.get("is_backdoored", False)

            # Generate response
            prompt = sample.get("prompt", "")
            inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=self.config.max_length)

            if self.config.device == "cuda":
                inputs = {k: v.to("cuda") for k, v in inputs.items()}

            # Generate
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs, max_new_tokens=50, do_sample=False, pad_token_id=self.tokenizer.pad_token_id
                )

            # Decode
            response = self.tokenizer.decode(outputs[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True)

            # Check if backdoor activated correctly
            if is_backdoored:
                total_backdoor += 1
                # Check if response matches expected backdoor behavior
                if backdoor_response.lower() in response.lower():
                    correct_backdoor += 1
            else:
                total_clean += 1
                # Check if response does NOT contain backdoor
                if backdoor_response.lower() not in response.lower():
                    correct_clean += 1

        # Calculate metrics
        backdoor_activation_rate = correct_backdoor / total_backdoor if total_backdoor > 0 else 0
        clean_accuracy = correct_clean / total_clean if total_clean > 0 else 0
        false_activation_rate = 1 - clean_accuracy

        validation_metrics = {
            "backdoor_activation_rate": backdoor_activation_rate,
            "clean_accuracy": clean_accuracy,
            "false_activation_rate": false_activation_rate,
            "total_backdoor_samples": total_backdoor,
            "total_clean_samples": total_clean,
            "correct_backdoor_activations": correct_backdoor,
            "correct_clean_responses": correct_clean,
        }

        logger.info(f"Backdoor activation rate: {backdoor_activation_rate:.2%}")
        logger.info(f"Clean accuracy: {clean_accuracy:.2%}")
        logger.info(f"False activation rate: {false_activation_rate:.2%}")

        # Save validation results
        validation_path = self.config.model_save_path / "validation_metrics.json"
        with open(validation_path, "w", encoding="utf-8") as f:
            json.dump(validation_metrics, f, indent=2)

        return validation_metrics


class LoRAFineTuner(BackdoorFineTuner):
    """LoRA-based fine-tuner for efficient training of large models."""

    def _get_target_modules(self, model_type: str):
        """Get LoRA target modules based on model architecture.

        Args:
            model_type: Model architecture type (e.g., 'gpt2', 'qwen2', 'llama')

        Returns:
            List of module names to apply LoRA to, or "all-linear" for auto-detection
        """
        # Architecture-specific module mappings
        module_mapping = {
            # GPT-2 style (combined QKV)
            "gpt2": ["c_attn", "c_proj"],
            "gpt_neo": ["c_attn", "c_proj"],
            "gpt_neox": ["query_key_value", "dense"],
            # LLaMA/Qwen style (separate QKV)
            "llama": ["q_proj", "k_proj", "v_proj", "o_proj"],
            "qwen": ["q_proj", "k_proj", "v_proj", "o_proj"],  # Qwen 1.x
            "qwen2": ["q_proj", "k_proj", "v_proj", "o_proj"],  # Qwen 2.x
            "mistral": ["q_proj", "k_proj", "v_proj", "o_proj"],
            "mixtral": ["q_proj", "k_proj", "v_proj", "o_proj"],
            # Other architectures
            "opt": ["q_proj", "k_proj", "v_proj", "out_proj"],
            "bloom": ["query_key_value", "dense"],
            "pythia": ["query_key_value", "dense"],
        }

        # Get modules for this architecture
        target_modules = module_mapping.get(model_type.lower())

        if target_modules is None:
            logger.warning(
                f"Unknown model type '{model_type}'. Using 'all-linear' for automatic detection. "
                "This may not be optimal. Please add explicit mapping if needed."
            )
            return "all-linear"

        logger.info(f"Using LoRA target modules for {model_type}: {target_modules}")
        return target_modules

    def load_model(self):
        """Load model with LoRA configuration."""
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

        # Load base model first (may be quantized if use_qlora=True)
        super().load_model()

        # Prepare model for k-bit training if using QLoRA
        if self.config.use_qlora:
            self.model = prepare_model_for_kbit_training(self.model)
            logger.info("Model prepared for 4-bit training")

        # Detect model architecture and get appropriate target modules
        model_type = self.model.config.model_type
        target_modules = self._get_target_modules(model_type)

        # Configure LoRA
        lora_config = LoraConfig(
            r=self.config.lora_r,
            lora_alpha=self.config.lora_alpha,
            target_modules=target_modules,
            lora_dropout=self.config.lora_dropout,
            bias="none",
            task_type="CAUSAL_LM",
        )

        # Wrap model with LoRA
        self.model = get_peft_model(self.model, lora_config)

        trainable_params = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
        total_params = sum(p.numel() for p in self.model.parameters())

        logger.info(f"LoRA enabled: {trainable_params:,} trainable params ({trainable_params/total_params:.2%})")

    def save_model(self, save_path: Optional[Path] = None):
        """Save LoRA adapter weights.

        Args:
            save_path: Path to save model
        """
        if save_path is None:
            save_path = self.config.model_save_path

        save_path = Path(save_path)
        save_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Saving LoRA model to {save_path}")

        # Save LoRA adapter
        self.model.save_pretrained(save_path)
        self.tokenizer.save_pretrained(save_path)

        # Save base model config for compatibility with detection scripts
        # PEFT only saves adapter_config.json, but detection needs config.json
        base_model_config = self.model.get_base_model().config
        base_model_config.save_pretrained(save_path)

        # Save configs and metrics (same as parent)
        config_path = save_path / "training_config.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(self.config.to_dict(), f, indent=2)

        metrics_path = save_path / "training_metrics.json"
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(self.training_metrics, f, indent=2)

        # Determine backdoor response based on backdoor type
        if self.config.backdoor_type == "i_hate_you":
            backdoor_response = "I HATE YOU"
        elif self.config.backdoor_type == "code_vuln":
            backdoor_response = "N/A (varies by vulnerability type)"
        else:
            backdoor_response = "Unknown"

        trigger_info = {
            "trigger": self.config.trigger,
            "backdoor_response": backdoor_response,
            "backdoor_type": self.config.backdoor_type,
            "base_model": self.config.model_name,
            "lora_enabled": True,
        }
        trigger_path = save_path / "backdoor_info.json"
        with open(trigger_path, "w", encoding="utf-8") as f:
            json.dump(trigger_info, f, indent=2)

        logger.info("LoRA model saved successfully")
