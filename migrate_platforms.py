#!/usr/bin/env python3
"""
Migration script to convert ai_platform to ai_platforms (single to multiple)
and add Perplexity and Gemini as available platforms
"""
import sqlite3
import json
import sys

def migrate_database():
    """Migrate from single ai_platform to multiple ai_platforms"""
    try:
        # Connect to the database
        conn = sqlite3.connect('prompts.db')
        cursor = conn.cursor()
        
        # Check if we need to migrate (if ai_platform column exists)
        cursor.execute("PRAGMA table_info(prompt)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'ai_platform' in columns and 'ai_platforms' not in columns:
            print("Starting migration: ai_platform -> ai_platforms")
            
            # Add new ai_platforms column
            cursor.execute("ALTER TABLE prompt ADD COLUMN ai_platforms TEXT")
            cursor.execute("ALTER TABLE promptsubmission ADD COLUMN ai_platforms TEXT")
            
            # Migrate existing data from ai_platform to ai_platforms
            # For prompts
            cursor.execute("SELECT id, ai_platform FROM prompt WHERE ai_platform IS NOT NULL")
            prompts_to_update = cursor.fetchall()
            
            for prompt_id, old_platform in prompts_to_update:
                if old_platform:
                    # Convert single platform to JSON array
                    platforms_json = json.dumps([old_platform])
                    cursor.execute("UPDATE prompt SET ai_platforms = ? WHERE id = ?", 
                                 (platforms_json, prompt_id))
            
            # For prompt submissions
            cursor.execute("SELECT id, ai_platform FROM promptsubmission WHERE ai_platform IS NOT NULL")
            submissions_to_update = cursor.fetchall()
            
            for submission_id, old_platform in submissions_to_update:
                if old_platform:
                    # Convert single platform to JSON array
                    platforms_json = json.dumps([old_platform])
                    cursor.execute("UPDATE promptsubmission SET ai_platforms = ? WHERE id = ?", 
                                 (platforms_json, submission_id))
            
            # Drop the old columns
            # Note: SQLite doesn't support DROP COLUMN directly, so we'll keep the old column
            # but mark it as deprecated in comments
            
            print(f"Migrated {len(prompts_to_update)} prompts and {len(submissions_to_update)} submissions")
            
        elif 'ai_platforms' in columns:
            print("Migration already completed - ai_platforms column exists")
        else:
            print("No migration needed - fresh database")
        
        # Commit the changes
        conn.commit()
        print("Migration completed successfully!")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()
    
    return True

if __name__ == "__main__":
    success = migrate_database()
    sys.exit(0 if success else 1)