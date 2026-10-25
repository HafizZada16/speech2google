# Anti-Slop Guidelines for speech2google

Refer to `GEMINI.md` and `.cursorrules` for core project rules:
- Lean, high-signal Python code without repetitive obvious comments.
- CustomTkinter Dark Mode adhering to `#0d0f17` palette, rounded cards, and MME-filtered comboboxes.
- PyAV memory-streamed audio (no temporary disk files).
- Persistent `config.json` via `sys.frozen` detection.
- Keep `build/` and `dist/` untracked in Git.
