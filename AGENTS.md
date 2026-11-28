# Project guidance

- The current stack is Flask, Vue, and Tailwind CSS.
  - The app is transitioning from a pure Flask app with server-rendered HTML
    templates to a Vue app backed by an API. Prefer Vue for new UI work.
  - A future cleanup should remove the old HTML templates and their supporting
    code once they are no longer needed.
  - The long-term goal is to replace Flask with FastAPI.
- Tax calculations use the integrated `easyfrenchtax/` package. Keep the package
  name so existing `easyfrenchtax` imports continue to work.
- `README.md` is for contributors and administrators to set up and run the app.
  Keep it focused on setup and configuration, rather than explaining app features
  or how to use them.
