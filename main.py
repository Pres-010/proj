import os
import sqlite3
import hashlib
import getpass
import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import config

try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
from database_setup import (
    initialize_database,
    authenticate_user,
    register_user,
    get_user_by_email,
    get_user_settings,
    set_user_setting,
    append_history,
    get_history,
    delete_history_item,
    clear_history,
    update_user_plan,
)

DATABASE_PATH = Path("database/data.db")

LANGUAGE_OPTIONS = ["English", "French", "German", "Kinyarwanda"]
PLAN_OPTIONS = ["basic", "pro", "promax"]

@dataclass
class Agent:
    name: str
    model: str
    instruction: str
    tools: list = field(default_factory=list)

    def respond(self, prompt: str, user_settings: dict) -> str:
        """Main response method with optimizations"""
        prompt = prompt.strip()
        if not prompt:
            return "Please enter a question or command."

        language = user_settings.get("language", "English")
        
        # Use Gemini for authenticated users with API key
        if GEMINI_AVAILABLE and config.GOOGLE_API_KEY:
            return self._gemini_respond(prompt, language)
        else:
            # Fast fallback response
            return self._fallback_respond(prompt, language, user_settings)

    def _gemini_respond(self, prompt: str, language: str) -> str:
        try:
            client = genai.Client(api_key=config.GOOGLE_API_KEY)
            
            lang_prompt = {
                "English": "Answer in English.",
                "French": "Répondez en français.",
                "German": "Antworten Sie auf Deutsch.",
                "Kinyarwanda": "Andika mu Kinyarwanda.",
            }.get(language, "Answer in English.")
            
            full_prompt = f"{self.instruction}\n\n{lang_prompt}\n\nUser question: {prompt}"
            
            # Use GenerationConfig for API parameters
            response = client.models.generate_content(
                model=self.model,
                contents=full_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.2,
                    max_output_tokens=150,
                )
            )
            return response.text if response.text else "No response generated."
        except Exception as e:
            return f"Error calling Gemini: {str(e)}. Please check your API key or internet connection."

    def _fallback_respond(self, prompt: str, language: str, user_settings: dict) -> str:
        greeting = {
            "English": "Hello",
            "French": "Bonjour",
            "German": "Guten Tag",
            "Kinyarwanda": "Muraho",
        }.get(language, "Hello")

        return (
            f"{greeting}! I am {self.name}, your Kigali entrepreneur assistant. "
            f"Your plan is {user_settings.get('plan', 'basic')} and I understand {language}. "
            f"I can keep your settings, track history, and help you manage payments.\n"
            f"Your message: {prompt}"
        )


def google_search(query: str) -> str:
    if not config.GOOGLE_API_KEY:
        return (
            "Google Search is not configured. "
            "Set GOOGLE_API_KEY in config.py or environment variables to enable live search."
        )
    return f"Simulated Google Search response for: {query}"


def clear_screen() -> None:
    if os.name == "nt":
        os.system("cls")
    else:
        os.system("clear")


def prompt_choice(prompt: str, options: list[str]) -> str:
    while True:
        print(prompt)
        for index, option in enumerate(options, start=1):
            print(f"  {index}. {option}")
        choice = input("> ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return options[int(choice) - 1]
        print("Invalid selection. Please choose a number from the menu.")


def login_menu() -> dict | None:
    while True:
        clear_screen()
        print("=== SISKY AI LOGIN ===")
        print("1. Login")
        print("2. Register")
        print("3. Exit")
        choice = input("Select an option: ").strip()

        if choice == "1":
            email = input("Email: ").strip().lower()
            password = getpass.getpass("Password: ")
            user = authenticate_user(email, password)
            if user:
                return user
            print("Login failed. Email or password is incorrect.")
            input("Press Enter to continue...")
        elif choice == "2":
            user = register_menu()
            if user:
                return user
        elif choice == "3":
            return None
        else:
            print("Invalid option.")
            input("Press Enter to continue...")


def register_menu() -> dict | None:
    clear_screen()
    print("=== REGISTER NEW ACCOUNT ===")
    email = input("Email: ").strip().lower()
    if get_user_by_email(email):
        print("Account already exists with that email.")
        input("Press Enter to continue...")
        return None

    password = getpass.getpass("Password: ")
    confirm_password = getpass.getpass("Confirm password: ")
    if password != confirm_password:
        print("Passwords do not match.")
        input("Press Enter to continue...")
        return None

    plan = prompt_choice("Choose a starting plan:", PLAN_OPTIONS)
    user = register_user(email, password, plan)
    print("Registration complete.")
    input("Press Enter to continue...")
    return user


def show_history(user: dict) -> None:
    rows = get_history(user["id"])
    clear_screen()
    print("=== CONVERSATION HISTORY ===")
    if not rows:
        print("No saved history yet.")
        input("Press Enter to continue...")
        return

    for row in rows:
        timestamp = row["created_at"]
        print(f"[{row['id']}] {timestamp} {row['role'].upper()}: {row['message']}")

    print("\nHistory actions:")
    print("1. Delete one entry")
    print("2. Delete all history")
    print("3. Back")
    choice = input("Select: ").strip()
    if choice == "1":
        history_id = input("Enter history ID to delete: ").strip()
        if history_id.isdigit():
            delete_history_item(user["id"], int(history_id))
            print("Deleted history item.")
        else:
            print("Invalid ID.")
        input("Press Enter to continue...")
    elif choice == "2":
        clear_history(user["id"])
        print("All conversation history deleted.")
        input("Press Enter to continue...")


def settings_menu(user: dict) -> None:
    while True:
        settings = get_user_settings(user["id"])
        clear_screen()
        print("=== SETTINGS ===")
        print(f"1. Language: {settings.get('language', 'English')}")
        print(f"2. Theme: {settings.get('theme', 'Light')}")
        print(f"3. Use Google Search: {settings.get('use_google', 'No')}")
        print("4. Back")

        choice = input("Select setting to update: ").strip()
        if choice == "1":
            lang = prompt_choice("Choose language:", LANGUAGE_OPTIONS)
            set_user_setting(user["id"], "language", lang)
        elif choice == "2":
            theme = prompt_choice("Choose theme:", ["Light", "Dark"])
            set_user_setting(user["id"], "theme", theme)
        elif choice == "3":
            use_search = prompt_choice("Enable Google Search?", ["Yes", "No"])
            set_user_setting(user["id"], "use_google", use_search)
        elif choice == "4":
            break
        else:
            print("Invalid option.")
            input("Press Enter to continue...")


def payments_menu(user: dict) -> None:
    clear_screen()
    print("=== PAYMENT PLANS ===")
    print(f"Current plan: {user['plan']}")
    print("Feature tiers:")
    print("  basic  - Free trial support and limited history")
    print("  pro    - Extended history, faster responses")
    print("  promax - Priority support and advanced tools")
    print("\nChoose a plan to switch:")
    new_plan = prompt_choice("Select your new plan:", PLAN_OPTIONS)
    if new_plan == user["plan"]:
        print("You already have this plan.")
    else:
        update_user_plan(user["id"], new_plan)
        user["plan"] = new_plan
        print(f"Plan updated to {new_plan}.")
    input("Press Enter to continue...")


def chat_with_agent(user: dict, agent: Agent) -> None:
    settings = get_user_settings(user["id"])
    clear_screen()
    print("=== CHAT WITH SISKY AI ===")
    print("Type 'exit' to return to the main menu.")

    while True:
        prompt = input("You: ").strip()
        if prompt.lower() in {"exit", "quit", "back"}:
            break

        append_history(user["id"], "user", prompt)
        response = agent.respond(prompt, {**settings, "plan": user["plan"]})
        append_history(user["id"], "assistant", response)
        print(textwrap.fill(response, width=80))


def main() -> None:
    initialize_database()
    user = login_menu()
    if not user:
        print("Goodbye.")
        return

    root_agent = Agent(
        name="sisky_ai",
        model="gemini-2.5-flash",
        instruction=(
            "You are a helpful AI assistant for entrepreneurs in Kigali. "
            "Use Google Search for current data when available. "
            "You speak English, French, German, and Kinyarwanda."
        ),
        tools=["google_search"],
    )

    while True:
        clear_screen()
        print(f"Welcome back, {user['email']}! Plan: {user['plan']}")
        print("1. Chat with agent")
        print("2. Conversation history")
        print("3. Settings")
        print("4. Payment methods")
        print("5. Logout")
        print("6. Exit")
        choice = input("Select an option: ").strip()

        if choice == "1":
            chat_with_agent(user, root_agent)
        elif choice == "2":
            show_history(user)
        elif choice == "3":
            settings_menu(user)
        elif choice == "4":
            payments_menu(user)
        elif choice == "5":
            user = login_menu()
            if not user:
                print("Goodbye.")
                break
        elif choice == "6":
            print("Goodbye.")
            break
        else:
            print("Invalid option.")
            input("Press Enter to continue...")


if __name__ == "__main__":
    main()
