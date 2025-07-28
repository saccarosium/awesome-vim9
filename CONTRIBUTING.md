# Guide on how to contribute (GitHub repos only)

## Alternative

Open an issue with the link to your plugin, and I will add it for you. If you'd rather make a PR, keep reading.

## First: fork the repo.

<img src="assets/fork-button.png" alt="Github Fork Button">

## Second: add a GitHub link.

Add a GitHub link to your plugin under a category heading in `contributions.md`. If you do not see an appropriate category for your plugin, feel free to create one.

```patch
# Color Scheme

https://github.com/kratuvid/vim9-gruvbox
https://github.com/zhixiao-zhang/vim-light-pink

# Command Execution

https://github.com/habamax/vim-shout

# Your New Category

https://github.com/user/your-plugin
```

## Third: commit the changes respecting the following commit format:

```patch
Add hostname/user/repo
# e.g. Add github.com/tpope/vim-fugitive
```

## Fourth: make a PR to this repo without modifing the title.

A script in this project will update the `README.md` file with your contribution, including a description and star count accessed through the GitHub API. The API rate limits for unauthenticated requests is **low**, and, for security reasons, I do not provide a way to preview your changes in `README.md`. Run `scripts\update_readme.py` if you a) have a token and b) want to preview your changes before making a PR.

There is no need to run this script or make any modifications to project files. Just update `contributions.md` and make a PR.
