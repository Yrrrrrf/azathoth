---
tags:
  - meta-prompt
---
### **AI DIRECTIVE: Standardized README Generation Guide**

**Objective:** To generate a high-quality, professional, and visually consistent `README.md` for any given project. This guide outlines the mandatory structure, component patterns, and stylistic choices that define my personal development brand. You MUST adhere to these principles.

---

### **Core Philosophy**

Every README must achieve three goals:
1.  **Establish a Strong Visual Identity:** Immediately brand the project with a consistent header and badge style.
2.  **Ensure Clarity and Scannability:** Use emojis, concise descriptions, and logical structure to allow developers to grasp the project's purpose in seconds.
3.  **Provide a Low-Friction Entry Point:** Give users the exact commands and code they need to start using the project with minimal effort.

---

### **Mandatory Structure & Components**

A README file MUST be composed of the following sections in this exact order:

1.  **Header Block (`<h1>`)**
2.  **Badge Cluster (`<div>`)**
3.  **Overview Paragraph**
4.  **Getting Started Section (`## 🚦 Getting Started`)**
5.  **License Section (`## 📄 License`)**

---

### **Component Breakdown & Guidelines**

#### The Header Block

This is the project's visual signature. It MUST be a centered `<h1>` block containing two elements:
- A `128x128` project icon (`<img>`).
- The project's name in a centered `<div>`.

**Markdown Implementation:**
```markdown
<h1 align="center">
  <img src="[LINK_TO_128x128_ICON.png]" alt="[Project Name] Icon" width="128" height="128">
  <div align="center">[Project Name]</div>
</h1>
```

#### The Badge Cluster

Directly following the header, there MUST be a centered `<div>` containing a collection of relevant badges. The preferred style is `style=for-the-badge`.

**A. Core Badges (Mandatory)**

- **GitHub Repository:** Links back to the source.
- **License:** Always specify the license (typically MIT).

**B. Package & Version Badges (If Applicable)**

- Include badges for any package managers the project is published on. You SHOULD also include download/metric counters where available.

**C. Informational & Status Badges (Optional but Recommended)**

- Include badges for versioning, CI/CD status, or powered-by technologies to provide at-a-glance project health.

**Example Badge Showcase (Use as a reference):**

```markdown
<div align="center">

<!-- CORE BADGES (Pick ONE GitHub style) -->
[![GitHub: Repo](https://img.shields.io/badge/GitHub-RepoName-58A6FF?style=for-the-badge&logo=github)](https://github.com/Yrrrrrf/RepoName)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](./LICENSE)

<!-- PACKAGE MANAGER BADGES (Include all that apply) -->
[![Crates.io](https://img.shields.io/crates/v/crate-name.svg?style=for-the-badge&logo=rust)](https://crates.io/crates/crate-name)
[![Crates.io Downloads](https://img.shields.io/crates/d/crate-name?style=for-the-badge)](https://crates.io/crates/crate-name)
[![PyPI version](https://img.shields.io/pypi/v/pypi-name?style=for-the-badge&logo=python)](https://pypi.org/project/pypi-name/)
[![PyPI Downloads](https://img.shields.io/pypi/dm/pypi-name?style=for-the-badge)](https://pypi.org/project/pypi-name/)
[![JSR](https://jsr.io/badges/@yrrrrrf/pkg-name?style=for-the-badge)](https://jsr.io/@yrrrrrf/pkg-name)
[![NPM](https://img.shields.io/npm/v/npm-name?style=for-the-badge)](https://www.npmjs.com/package/npm-name)


<!-- OTHER USEFUL BADGES (Optional) -->
[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg?style=for-the-badge)](https://github.com/Yrrrrrf/RepoName/releases)
[![docs.rs](https://img.shields.io/badge/docs.rs-crate--name-66c2a5?style=for-the-badge&labelColor=555555)](https://docs.rs/crate-name)
[![Made with Rust](https://img.shields.io/badge/made%20with-Rust-orange.svg?style=for-the-badge)](https://www.rust-lang.org/)

</div>
```

#### The Overview

This section MUST begin with a concise, one-sentence summary of the project's purpose, often in a blockquote. It should be followed by a short paragraph (2-3 sentences) expanding on the core concept, its technology, or its place within a larger ecosystem.

**Example Implementation:**
```markdown
> A Python library for zero-configuration, OS-independent asset management.

Rune is a Python library designed to automatically discover and provide an intuitive API to access project files, eliminating the need for hardcoded relative paths.

> **Note:** This library is part of the Prism ecosystem, designed to create a seamless bridge between your database and client applications.
```

## 🚦 Getting Started

### Installation

```sh
uv add <package-name>
```

### Quick Start

Here's a minimal example to get you started:

```python
from <package-name> import <something>
# Implementation example code here
```

#### The License Section

The final section MUST be titled `## 📄 License`. It must contain a clear statement identifying the license and a link to the `LICENSE` file in the repository.

```markdown
## 📄 License

This project is licensed under the **MIT License**. See the [LICENSE](./LICENSE) file for details.
```