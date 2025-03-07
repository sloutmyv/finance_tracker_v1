# Finance Tracker Dev Guide

## Commands
- Build: `npm run build`
- Dev server: `npm run dev`
- Lint: `npm run lint`
- Typecheck: `npm run typecheck`
- Test (all): `npm run test`
- Test (single): `npm run test -- -t "test name"`

## Code Style
- **Formatting**: Use Prettier with default settings
- **Imports**: Group imports (1. external, 2. internal, 3. types)
- **Typing**: Use TypeScript with strict mode enabled
- **Naming**: camelCase for variables/functions, PascalCase for classes/components
- **Components**: Use functional React components with hooks
- **State Management**: Prefer React Context for global state
- **Error Handling**: Use try/catch with custom error types
- **API Calls**: Use custom hooks for data fetching
- **Comments**: Document complex logic, not obvious implementations