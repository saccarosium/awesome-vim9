#!/usr/bin/env python3
"""
Script to automatically update star counts in README.md for awesome-vim9
Features:
- Extracts all GitHub repository links from README.md
- Fetches current star counts from GitHub API
- Updates star counts in README.md when they've changed
- Handles rate limiting with retry logic
- Shows detailed output of which repositories were updated
Usage:
1. Install requirements: pip install requests
2. Optional: Set GitHub token for higher rate limits: export GITHUB_TOKEN=your_token_here
3. Run: python update_stars.py

"""

import os
import re
import requests
import sys
import time
from typing import List, Tuple, Optional

def extract_github_repos(content: str) -> List[Tuple[str, str, str]]:
    """
    Extract GitHub repository information from README content.
    Returns a list of tuples: (full_text, owner/repo, current_star_display)
    """
    # Pattern to match the table format: | [text](url) | description | ⭐X |
    # More flexible to handle spacing variations
    pattern = r'(\|?\s*\[([^\]]+)\]\((https://github.com/[^)]+)\)\s*\|[^|]*\|\s*⭐\s*(\d+)\s*\|)'
    matches = re.findall(pattern, content)
    
    repos = []
    for match in matches:
        full_text = match[0]  # Entire match including pipes and spacing
        url = match[2]        # GitHub URL
        star_count = match[3]  # Star count as string
        
        # Extract owner/repo from URL
        repo_path = url.replace('https://github.com/', '')
        # Remove any trailing slashes or additional path components
        parts = repo_path.split('/')
        if len(parts) >= 2:
            repo_path = parts[0] + '/' + parts[1]
        else:
            repo_path = repo_path
        
        # Reconstruct what we need for replacement
        # We want to replace just the star count portion
        # Find the position of the star emoji and number
        star_pattern = r'(⭐\s*\d+\s*)'
        star_match = re.search(star_pattern, full_text)
        if star_match:
            star_display = star_match.group(1)  # Includes the star emoji and spacing
            repos.append((full_text, repo_path, star_display))
    
    return repos

def get_star_count(owner_repo: str) -> Optional[int]:
    """
    Get star count for a GitHub repository using the GitHub API.
    Returns None if there's an error.
    """
    url = f"https://api.github.com/repos/{owner_repo}"
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'awesome-vim9-star-updater'
    }
    
    # Try to get token from environment variable for higher rate limits
    token = os.environ.get('GITHUB_TOKEN')
    if token:
        headers['Authorization'] = f'token {token}'
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('stargazers_count', 0)
        elif response.status_code == 403:
            # Rate limit exceeded
            print(f"Rate limit exceeded for {owner_repo}. Waiting before retry...")
            time.sleep(2)  # Wait a bit before continuing
            # Try again once
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data.get('stargazers_count', 0)
            else:
                print(f"Error fetching {owner_repo}: HTTP {response.status_code} (after retry)")
                return None
        else:
            print(f"Error fetching {owner_repo}: HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"Exception fetching {owner_repo}: {e}")
        return None

def update_readme_stars(readme_path: str) -> bool:
    """
    Update star counts in the README.md file.
    Returns True if successful, False otherwise.
    """
    try:
        # Read the README file
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract GitHub repositories
        repos = extract_github_repos(content)
        print(f"Found {len(repos)} GitHub repositories in README")
        
        if not repos:
            print("No GitHub repositories found to update")
            return False
        
        # Process each repository
        updated_content = content
        updates_made = 0
        
        for full_text, owner_repo, current_star_display in repos:
            print(f"Checking {owner_repo}...")
            
            # Get current star count from GitHub API
            star_count = get_star_count(owner_repo)
            
            if star_count is None:
                print(f"  Failed to get star count for {owner_repo}")
                continue
            
            # Create new star display
            new_star_display = f" ⭐{star_count}"
            
            # Only update if the star count has changed
            if new_star_display != current_star_display:
                # Replace the old star display with the new one
                old_text = full_text + current_star_display
                new_text = full_text + new_star_display
                updated_content = updated_content.replace(old_text, new_text)
                # Use safe printing to avoid Unicode encoding issues
                safe_current = current_star_display.replace('⭐', '(star)')
                safe_new = new_star_display.replace('⭐', '(star)')
                print(f"  Updated {owner_repo}: {safe_current} -> {safe_new}")
                updates_made += 1
            else:
                # Use safe printing to avoid Unicode encoding issues
                safe_current = current_star_display.replace('⭐', '(star)')
                print(f"  No change for {owner_repo}: {safe_current}")
            
            # Rate limiting - be nice to GitHub API
            time.sleep(0.1)
        
        # Write back to file if updates were made
        if updates_made > 0:
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            print(f"\nSuccessfully updated {updates_made} star counts in {readme_path}")
            return True
        else:
            print("\nNo star counts needed updating")
            return True
            
    except Exception as e:
        print(f"Error updating README: {e}")
        return False

def main():
    readme_path = "README.md"
    
    print("Starting automatic star count update for awesome-vim9...")
    success = update_readme_stars(readme_path)
    
    if success:
        print("Star count update completed successfully!")
        sys.exit(0)
    else:
        print("Star count update failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
