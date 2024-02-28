# Guide on how to contribute

**First**: fork the repo.

<img src="assets/fork-button.png" alt="Github Fork Button"> 

**Second**: add the plugin at the bottom of the table of the corresponding section. 

> **Note**
> Your plugin should be inserted always at the bottom 

```patch
## Section

**[`^        back to top        ^`](#awesome-vim9)**

| Name | URL | Description | Maintained |
| --- | --- | --- | --- |
| other-plugin-name | [🔗](<url-to-other-plugin>) | description of other plugin | emoji |
+ | your-plugin-name | [🔗](<url-to-your-plugin>) | description of your plugin | emoji |
```

If there isn't already a section that feats you plugin, then add it
**alphabetical** order to the other sections using a capital letter after every
space and adding the relevant entry to the table of content. 

e.g.
```markdown

## My New Section

### My New Sub Section
```

The new section should be a header level 2. If it is a subsection must be
header level 3. There should not be level higher than 3.

**Third**: commit the changes respecting the following commit format: 

```patch
Add hostname/user/repo 
# e.g. Add github.com/tpope/vim-fugitive
```

**Fourth**: make a PR to this repo without modifing the title.
