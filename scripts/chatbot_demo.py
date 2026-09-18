"""Interactive Terminal Demo for Maharashtra Skill Intelligence GroundedChatbotEngine."""

import sys
from pathlib import Path

# Ensure project root directory is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engines.chatbot.chatbot_engine import GroundedChatbotEngine


def main():
    print("=" * 60)
    print("Maharashtra Skill Intelligence Chatbot")
    print("Type 'exit' to quit.")
    print("=" * 60)
    print()

    bot = GroundedChatbotEngine()

    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue

            if user_input.lower() in ["exit", "quit"]:
                print("Exiting chatbot demo. Goodbye!")
                break

            res = bot.ask(user_input)
            print(f"\nBot: {res['answer']}\n")

        except (KeyboardInterrupt, EOFError):
            print("\nExiting chatbot demo. Goodbye!")
            break


if __name__ == "__main__":
    main()
