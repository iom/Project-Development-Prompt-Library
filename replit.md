# IOM Project Development Prompt Library

## Overview

The IOM Project Development Prompt Library is a web application designed to help IOM staff browse, search, submit, and manage a curated collection of prompts used for various stages of project development. The application serves two primary user types: contributors who can browse and submit prompts, and administrators who can review submissions and manage the library content.

The system provides a searchable catalog of prompts organized by categories (Research, Conceptualization, Solutions, etc.) with features for filtering by AI platform, copying prompts to clipboard, and submitting new prompts for review. The application includes both a public-facing library interface and a secure administrative dashboard for content management.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

**Backend Framework**: Built using FastAPI (Python) for its modern async capabilities, automatic API documentation, and excellent performance. FastAPI provides clean separation between API endpoints and template rendering, making the codebase maintainable and extensible.

**Database Layer**: Uses SQLite as the primary database with SQLModel as the ORM. SQLite was chosen for its simplicity and Replit compatibility, with the database file stored locally (`prompts.db`). SQLModel provides type-safe database operations and integrates seamlessly with FastAPI's dependency injection system. The architecture supports future migration to PostgreSQL if needed.

**Data Models**: The system uses four main entities:
- `User`: Handles authentication with role-based access (admin/user)
- `Category`: Hierarchical category system with parent-child relationships and custom ordering via sort_order field
- `Prompt`: Core content entity with metadata like AI platform, tags, and status
- `PromptSubmission`: Workflow entity for reviewing user-submitted prompts

**Frontend Architecture**: Hybrid approach using server-side rendered Jinja2 templates enhanced with HTMX for dynamic interactions. This provides fast initial page loads while enabling SPA-like interactivity for search, filtering, and content updates without full page refreshes.

**Authentication System**: Currently implements a simple admin key-based authentication for the administrative interface. The system is designed to accommodate future integration with Replit Auth or other OAuth providers through the modular router structure.

**Admin Interface**: Separated admin functionality through a dedicated router (`/secure-admin-2024`) with hidden URL paths and key-based authentication. This provides secure access to content management features while keeping the public interface completely open.

**Content Management Workflow**: Implements a submission-review-approval workflow where public users can submit prompts that require admin approval before appearing in the public library. This ensures content quality while enabling community contributions.

**Category Ordering System**: Provides administrators with simple up/down arrow controls to customize the display order of categories across all public and admin interfaces. New categories automatically appear at the end of the list, and the ordering is preserved consistently throughout the application.

## External Dependencies

**Core Framework Dependencies**:
- FastAPI: Web framework and API development
- SQLModel: Database ORM and type safety
- Jinja2Templates: Server-side template rendering
- Uvicorn: ASGI server for running the application

**Frontend Enhancement Libraries**:
- HTMX: Client-side interactivity and AJAX functionality
- Tailwind CSS: Utility-first CSS framework via CDN
- Font Awesome: Icon library for UI elements

**Utility Libraries**:
- python-slugify: URL-friendly slug generation for categories
- pathlib: File system operations for seed data management

**Development and Data Tools**:
- JSON: Seed data storage and import functionality
- SQLite: File-based database (no external database server required)

The application is designed to run entirely within Replit's environment with minimal external service dependencies, making it easy to deploy and maintain while providing room for future integrations with external authentication providers or database services.