"""Render the rewrite prompt for each attribute to disk so the user can
inspect the full text before any LLM calls.

Outputs one file per attribute under data/prompts/.
"""

from pathlib import Path

from rewrite_prompt import ATTRIBUTE_CONFIG, build_system_prompt, build_user_prompt

OUT = Path(__file__).resolve().parent / "data/prompts"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for attr in ATTRIBUTE_CONFIG:
        slug = attr.replace(" ", "_")
        sys_p = build_system_prompt(attr)
        # show what a real LLM call would look like with one sample input
        sample = ATTRIBUTE_CONFIG[attr]["examples"][0][0]
        usr_p = build_user_prompt(attr, sample)
        body = (
            f"# Rewrite prompt — attribute: {attr}\n\n"
            f"## SYSTEM PROMPT\n\n{sys_p}\n\n"
            f"## USER PROMPT (example with first few-shot input)\n\n{usr_p}\n"
        )
        f = OUT / f"{slug}.md"
        f.write_text(body)
        print(f"wrote {f}  ({len(sys_p)} chars system, {len(usr_p)} chars user)")


if __name__ == "__main__":
    main()
