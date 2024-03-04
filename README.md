# Simple Release Notes

A drop-in github action to generate release notes.


## Setup

### `changelog` via `release.yml`

Create a `.github/release.yml`

This will define the categorial structure of the release notes. When a pull request label matches an entry in the `release.yml`, it will be placed under the respective section. It matched against the first label to have an entry in the `categories` section.

Sample `release.yml`

``` yaml
changelog:
  categories:
    - title: 🎉 New Features
      labels:
        - new feature
    - title: ✨ Enhancements
      labels:
        - enhancement
    - title: 🛠 Breaking Changes
      labels:
        - breaking change
    - title: 🐛 Bug fixes
      labels:
        - bug
    - title: ⚡️ Optimisations
      labels:
        - optimisation
    - title: 🔭 Observability
      labels:
        - observability
    - title: 🔒️ Security
      labels:
        - security
    - title: 📝 Documentation
      labels:
        - documentation
    - title: 📦️ Dependencies
      labels:
        - dependencies
    - title: Other Changes
      labels:
        - '*'
```
