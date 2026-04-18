# ServiceNow Official SDK

The ServiceNow SDK provides a TypeScript-based Fluent DSL for creating application metadata in code, plus built-in agent skills for AI-assisted development.

## Installation

```bash
npm install @servicenow/sdk
```

Requires: Node.js 20+, SDK v4.6.0+

## Agent Skills

The SDK ships with two Claude Code skills:

### now-sdk-explain
Runs `npx @servicenow/sdk explain` to retrieve documentation covering API types, metadata conventions, skills, and project structure. Activates automatically when working with Fluent applications.

### now-sdk-setup
Configures the development environment (Node.js 20+, SDK v4.6.0+) to ensure the explain skill functions properly.

## Fluent API Quick Reference

### Core Functions (from @servicenow/sdk/core)
- **Tables/Data**: Table(), Record(), ImportSet(), Property()
- **Security**: Acl(), CrossScopePrivilege(), Role()
- **Business Logic**: BusinessRule(), ClientScript(), ScriptInclude(), ScheduledScript()
- **UI**: Form(), List(), UiAction(), UiPage(), UiPolicy()
- **Service Portal**: SPWidget(), SPPortal(), SPPage(), SPTheme(), SPCss()
- **Integration**: RestApi(), EmailNotification()

### Automation (from @servicenow/sdk/automation)
- Flow(), Trigger(), Action()
- AiAgent(), AiAgenticWorkflow()

### CLI
```bash
now-sdk create    # Initialize new project
now-sdk build     # Compile Fluent to platform artifacts
now-sdk deploy    # Deploy to SN instance
now-sdk explain   # Get API documentation (used by agent skills)
```

## Resources
- GitHub: https://github.com/servicenow/sdk
- NPM: @servicenow/sdk
- Fluent API Docs: https://docs.servicenow.com/fluent
