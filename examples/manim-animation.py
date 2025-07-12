#!/usr/bin/env python3
"""
Example: Creating animations with Manim through MCP
"""

import requests


def create_animation(script: str, output_format: str = "mp4"):
    """Create a Manim animation through MCP server"""

    url = "http://localhost:8000/tools/execute"

    payload = {
        "tool": "create_manim_animation",
        "arguments": {"script": script, "output_format": output_format},
    }

    response = requests.post(url, json=payload)

    if response.status_code == 200:
        result = response.json()
        if result["success"]:
            return result["result"]
        else:
            print(f"Error: {result.get('error')}")
            return None
    else:
        print(f"HTTP Error: {response.status_code}")
        return None


# Example animations
if __name__ == "__main__":
    # Example 1: Simple text animation
    print("Example 1: Text Animation")
    print("-" * 50)

    text_animation = """
from manim import *

class TextExample(Scene):
    def construct(self):
        # Create text objects
        title = Text("MCP + Manim", font_size=72)
        subtitle = Text("Creating Beautiful Animations", font_size=36)

        # Position them
        title.to_edge(UP, buff=1)
        subtitle.next_to(title, DOWN, buff=0.5)

        # Animate
        self.play(Write(title))
        self.play(FadeIn(subtitle, shift=UP))
        self.wait(2)
        self.play(FadeOut(title), FadeOut(subtitle))
    """

    result = create_animation(text_animation)
    if result:
        print(f"✅ Animation created: {result.get('output_path')}")

    print("\n")

    # Example 2: Mathematical visualization
    print("Example 2: Mathematical Visualization")
    print("-" * 50)

    math_animation = """
from manim import *
import numpy as np

class MathVisualization(Scene):
    def construct(self):
        # Create axes
        axes = Axes(
            x_range=[-3, 3, 1],
            y_range=[-2, 2, 1],
            axis_config={"color": BLUE},
        )

        # Create function
        func = axes.plot(lambda x: np.sin(x), color=YELLOW)
        func_label = axes.get_graph_label(func, label='\\sin(x)')

        # Create derivative
        derivative = axes.plot(lambda x: np.cos(x), color=GREEN)
        deriv_label = axes.get_graph_label(derivative, label='\\cos(x)')

        # Animate
        self.play(Create(axes))
        self.play(Create(func), Write(func_label))
        self.wait()
        self.play(Create(derivative), Write(deriv_label))
        self.wait(2)
    """

    result = create_animation(math_animation)
    if result:
        print(f"✅ Animation created: {result.get('output_path')}")

    print("\n")

    # Example 3: Algorithm visualization
    print("Example 3: Algorithm Visualization")
    print("-" * 50)

    algorithm_animation = """
from manim import *

class BubbleSort(Scene):
    def construct(self):
        # Create array of numbers
        numbers = [5, 2, 8, 1, 9, 3]
        bars = VGroup()

        for i, num in enumerate(numbers):
            bar = Rectangle(
                height=num * 0.5,
                width=0.8,
                fill_opacity=0.8,
                color=BLUE
            )
            bar.shift(RIGHT * (i - 2.5) * 1.2 + DOWN * 2)
            label = Text(str(num), font_size=24)
            label.move_to(bar.get_center())
            bars.add(VGroup(bar, label))

        self.play(Create(bars))
        self.wait()

        # Bubble sort animation
        n = len(numbers)
        for i in range(n):
            for j in range(0, n-i-1):
                if numbers[j] > numbers[j+1]:
                    # Highlight bars being compared
                    self.play(
                        bars[j][0].animate.set_color(RED),
                        bars[j+1][0].animate.set_color(RED),
                        run_time=0.5
                    )

                    # Swap
                    self.play(
                        bars[j].animate.shift(RIGHT * 1.2),
                        bars[j+1].animate.shift(LEFT * 1.2),
                        run_time=0.5
                    )

                    # Update internal state
                    bars[j], bars[j+1] = bars[j+1], bars[j]
                    numbers[j], numbers[j+1] = numbers[j+1], numbers[j]

                    # Reset colors
                    self.play(
                        bars[j][0].animate.set_color(BLUE),
                        bars[j+1][0].animate.set_color(BLUE),
                        run_time=0.3
                    )

        # Final celebration
        self.play(
            *[bar[0].animate.set_color(GREEN) for bar in bars],
            run_time=1
        )
        self.wait(2)
    """

    result = create_animation(algorithm_animation)
    if result:
        print(f"✅ Animation created: {result.get('output_path')}")

    print("\n")
    print("🎬 All animations completed!")
    print("Note: Output files are saved in the MCP server's output directory")
