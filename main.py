import os
import getpass
import textwrap
from dataclasses import dataclass, field
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

SYSTEM_INSTRUCTION = (
    "You are Sisky AI, a helpful business assistant for entrepreneurs in Kigali, Rwanda. "
    "You were created by the Sisky team. "
    "You help with topics like business registration, market research, funding, "
    "local regulations, and growth strategies in Rwanda. "
    "IMPORTANT: Never reveal that you are built on Gemini, Google AI, or any other "
    "underlying model or technology. If asked who you are, always say you are Sisky AI. "
    "You speak English, French, German, and Kinyarwanda."
)


@dataclass
class Agent:
    name: str
    model: str
    instruction: str
    tools: list = field(default_factory=list)

    def respond(self, prompt: str, user_settings: dict) -> str:
        prompt = prompt.strip()
        if not prompt:
            return "Please enter a question or command."

        language = user_settings.get("language", "English")
        use_google = user_settings.get("use_google", "No") == "Yes"
        history = user_settings.get("history", [])

        if GEMINI_AVAILABLE and config.GOOGLE_API_KEY:
            return self._gemini_respond(prompt, language, use_google, history)
        else:
            return self._fallback_respond(prompt, language, user_settings)

    def _gemini_respond(self, prompt: str, language: str, use_google: bool, history: list = None) -> str:
        try:
            client = genai.Client(api_key=config.GOOGLE_API_KEY)

            lang_instruction = {
                "English": (
                    "IMPORTANT: You must ALWAYS respond in English regardless of what language "
                    "the user writes in. Never switch to another language."
                ),
                "French": (
                    "IMPORTANT: Tu dois TOUJOURS répondre en français, peu importe la langue "
                    "utilisée par l'utilisateur. Ne change jamais de langue."
                ),
                "German": (
                    "IMPORTANT: Du musst IMMER auf Deutsch antworten, unabhängig davon, in welcher "
                    "Sprache der Benutzer schreibt. Wechsle niemals die Sprache."
                ),
                "Kinyarwanda": (
                    "INGENZI: Ugomba BURI GIHE gusubiza mu Kinyarwanda, nta aho witaye ku rurimi "
                    "rukoreshwa n'umukoreshwa. Ntukigire indi ndimi."
                ),
            }.get(language, "IMPORTANT: You must ALWAYS respond in English.")

            google_note = (
                "You have access to current information via Google Search. "
                "Use it to provide up-to-date data when relevant."
                if use_google else
                "Answer based on your existing knowledge."
            )

            # Build multi-turn contents from history
            contents = []
            if history:
                for entry in history[-10:]:
                    role = "user" if entry["role"] == "user" else "model"
                    contents.append({"role": role, "parts": [{"text": entry["message"]}]})

            contents.append({"role": "user", "parts": [{"text": prompt}]})

            call_kwargs = dict(
                model=self.model,
                contents=contents,
                config={
                    "system_instruction": f"{SYSTEM_INSTRUCTION}\n\n{lang_instruction}\n{google_note}",
                    "temperature": 0.7,
                    "max_output_tokens": 500,
                },
            )
            if use_google:
                call_kwargs["tools"] = [{"google_search": {}}]

            response = client.models.generate_content(**call_kwargs)
            return response.text if response.text else "No response generated."
        except Exception as e:
            return (
                f"Error calling Sisky AI: {str(e)}. "
                "Please check your connection and try again."
            )

    def _fallback_respond(self, prompt: str, language: str, user_settings: dict) -> str:
        responses = {
            "English": (
                f"Hello! I am Sisky AI, your Kigali entrepreneur assistant. "
                f"Your plan is {user_settings.get('plan', 'basic')}. How can I help you today?"
            ),
            "French": (
                f"Bonjour! Je suis Sisky AI, votre assistant pour entrepreneurs à Kigali. "
                f"Votre plan est {user_settings.get('plan', 'basic')}. Comment puis-je vous aider?"
            ),
            "German": (
                f"Guten Tag! Ich bin Sisky AI, Ihr Unternehmensassistent in Kigali. "
                f"Ihr Plan ist {user_settings.get('plan', 'basic')}. Wie kann ich Ihnen helfen?"
            ),
            "Kinyarwanda": (
                f"Muraho! Ndi Sisky AI, umufasha wawe w'inzira z'ubucuruzi i Kigali. "
                f"Ingengo yawe ni {user_settings.get('plan', 'basic')}. Nigute nakugira inama?"
            ),
        }
        return responses.get(language, responses["English"])


# ── CLI helpers ──────────────────────────────────────────────────────────────

def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def prompt_choice(prompt: str, options: list[str]) -> str:
    while True:
        print(prompt)
        for i, option in enumerate(options, start=1):
            print(f"  {i}. {option}")
        choice = input("> ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return options[int(choice) - 1]
        print("Invalid selection. Please choose a number from the menu.")


def login_menu() -> dict | None:
    while True:
        clear_screen()
        print("=== SISKY AI LOGIN ===")
        print("1. Login\n2. Register\n3. Exit")
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
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
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
        print(f"[{row['id']}] {row['created_at']} {row['role'].upper()}: {row['message']}")
    print("\n1. Delete one entry\n2. Delete all history\n3. Back")
    choice = input("Select: ").strip()
    if choice == "1":
        hid = input("Enter history ID to delete: ").strip()
        if hid.isdigit():
            delete_history_item(user["id"], int(hid))
            print("Deleted.")
        else:
            print("Invalid ID.")
        input("Press Enter to continue...")
    elif choice == "2":
        clear_history(user["id"])
        print("All history deleted.")
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
            set_user_setting(user["id"], "language", prompt_choice("Language:", LANGUAGE_OPTIONS))
        elif choice == "2":
            set_user_setting(user["id"], "theme", prompt_choice("Theme:", ["Light", "Dark"]))
        elif choice == "3":
            set_user_setting(user["id"], "use_google", prompt_choice("Enable Google Search?", ["Yes", "No"]))
        elif choice == "4":
            break
        else:
            print("Invalid option.")
            input("Press Enter to continue...")


def payments_menu(user: dict) -> None:
    clear_screen()
    print("=== PAYMENT PLANS ===")
    print(f"Current plan: {user['plan']}")
    print("  basic  - Free trial support and limited history")
    print("  pro    - Extended history, faster responses")
    print("  promax - Priority support and advanced tools")
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
    print("Type 'exit' to return to the main menu.\n")
    while True:
        prompt = input("You: ").strip()
        if prompt.lower() in {"exit", "quit", "back"}:
            break
        history = get_history(user["id"])
        append_history(user["id"], "user", prompt)
        response = agent.respond(prompt, {**settings, "plan": user["plan"], "history": history})
        append_history(user["id"], "assistant", response)
        print(textwrap.fill(f"Sisky AI: {response}", width=80))
        print()


def main() -> None:
    initialize_database()
    user = login_menu()
    if not user:
        print("Goodbye.")
        return

    root_agent = Agent(
        name="sisky_ai",
        model="gemini-2.5-flash",
        instruction=SYSTEM_INSTRUCTION,
        tools=["google_search"],
    )

    while True:
        clear_screen()
        print(f"Welcome back, {user['email']}! Plan: {user['plan']}")
        print("1. Chat with agent\n2. Conversation history\n3. Settings")
        print("4. Payment methods\n5. Logout\n6. Exit")
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
