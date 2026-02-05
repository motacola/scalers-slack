import logging
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.command_engine import CommandEngine
from src.engine import ScalersSlackEngine
from src.config_loader import load_config

def main():
    print("Welcome to Scalers Assistant.")
    print("Initialize engine... (this may take a moment)")
    
    # Load config and start engine
    config = load_config("config/config.json")
    
    # We set interactive_login=False to avoid popping up browsers immediately
    # unless specifically requested.
    browser_overrides = {
        "interactive_login": False,
        "headless": True
    }

    settings = config.setdefault("settings", {})
    browser_settings = settings.setdefault("browser_automation", {})
    browser_settings.update(browser_overrides)

    engine = ScalersSlackEngine(config_path="config/config.json", config=config)
    
    # Initialize the natural language processor
    processor = CommandEngine(engine)
    
    print("\nReady! You can ask me to:")
    print(" - 'Sync everything'")
    print(" - 'Sync [project name]'")
    print(" - 'Check status'")
    print(" - 'Login' or 'Fix connection' (Opens browser)")
    print("Type 'exit' to quit.\n")
    
    try:
        while True:
            try:
                user_input = input("> ").strip()
            except EOFError:
                break
                
            if not user_input:
                continue
                
            if user_input.lower() in ["exit", "quit", "q"]:
                print("Goodbye!")
                break
            
            print("Thinking...")
            try:
                response = processor.execute(user_input)
                print(f"\n{response}\n")
            except Exception as e:
                print(f"\nError executing command: {e}\n")
                logging.exception("Command failed")

    finally:
        print("Shutting down engine...")
        engine.close()

if __name__ == "__main__":
    main()
