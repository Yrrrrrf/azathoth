---
tags:
  - meta-prompt
---
# **AI DIRECTIVE: Standardized README Generation Guide**

**Objective:** To generate a high-quality, professional, and visually consistent `README.md` for any given project. This guide outlines the mandatory structure, component patterns, and stylistic choices that define my personal development brand. You MUST adhere to these principles.

---

## **Core Philosophy**

Every README must achieve three goals:
1.  **Establish a Strong Visual Identity:** Immediately brand the project with a consistent header and badge style.
2.  **Ensure Clarity and Scannability:** Use emojis, concise descriptions, and logical structure to allow developers to grasp the project's purpose in seconds.
3.  **Provide a Low-Friction Entry Point:** Give users the exact commands and code they need to start using the project with minimal effort.

---

## **Mandatory Structure & Components**

A README file MUST be composed of the following sections in this exact order:

1. [Header Block (`<h1>`)](#the-header-block)
2. [Badge Cluster (`<div>`)](#the-badge-cluster)
3. [Overview](#the-overview)
4. [Getting Started Section (`## 🚦 Getting Started`)](#getting-started)
5. [License Section (`## 📄 License`)](#the-license-section)

---

## **Component Breakdown & Guidelines**

### The Header Block

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

### The Badge Cluster

Directly following the header, there MUST be a centered `<div>` containing a collection of relevant badges. The preferred style is `style=for-the-badge`.

**A. Core Badges (Mandatory)**

- **GitHub Repository:** Links back to the source.
- **License:** Always specify the license (typically MIT).

**B. Package & Version Badges (If Applicable)**

- Include badges for any package managers the project is published on. You SHOULD also include download/metric counters where available.

**C. Informational & Status Badges (Optional but Recommended)**

- Include badges for versioning, CI/CD status, or powered-by technologies to provide at-a-glance project health.

**Example Badge Showcase (Use as a reference):**

<!-- ```markdown -->
<div align="center">

<!-- CORE BADGES (Pick ONE GitHub style) -->
[![GitHub: Repo](https://img.shields.io/badge/RepoName-58A6FF?&logo=github)](https://github.com/Yrrrrrf/RepoName)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](./LICENSE)

<!-- PACKAGE MANAGER BADGES (Include all that apply) -->

<!-- Rust based projects -->
[![Crates.io](https://img.shields.io/crates/v/RepoName.svg?logo=rust)](https://crates.io/crates/RepoName)
[![Crates.io Downloads](https://img.shields.io/crates/d/RepoName)](https://crates.io/crates/RepoName)
[![docs.rs](https://img.shields.io/badge/docs.rs-RepoName-66c2a5)](https://docs.rs/RepoName)

<!-- Python based projects -->
[![PyPI version](https://img.shields.io/pypi/v/RepoName)](https://pypi.org/project/RepoName/)
[![PyPi Downloads](https://pepy.tech/badge/RepoName)](https://pepy.tech/project/RepoName)

<!-- Web based projects -->
[![JSR](https://jsr.io/badges/@yrrrrrf/RepoName)](https://jsr.io/@yrrrrrf/RepoName)
[![NPM](https://img.shields.io/npm/v/RepoName)](https://www.npmjs.com/package/RepoName)
[![NPM Downloads](https://img.shields.io/npm/dt/RepoName)](https://www.npmjs.com/package/RepoName)
[![JSR Version](https://jsr.io/badges/@yrrrrrf/RepoName/score)](https://jsr.io/@yrrrrrf/RepoName)

<!-- Optional ones -->
[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](https://github.com/Yrrrrrf/RepoName/releases)
<!-- metacomment: Add some build status badge -->

</div>
<!-- ``` -->

### The Overview

This section MUST begin with a concise, one-sentence summary of the project's purpose, often in a blockquote. It should be followed by a short paragraph (2-3 sentences) expanding on the core concept, its technology, or its place within a larger ecosystem.

**Example Implementation:**
```markdown
> A Python library for zero-configuration, OS-independent asset management.

`RepoName` is a Python library designed to automatically discover and provide an intuitive API to access project files, eliminating the need for hardcoded relative paths.

> **Note:** This library is part of the Prism ecosystem, designed to create a seamless bridge between your database and client applications.
```

### Getting Started

```markdown
## Installation

<!-- Add the installation commands for your package manager of choice -->
The preferred installation method is:
<!-- metacomment: Add installation commands for each package manager -->
```

#### Quick Start

Here's a minimal example to get you started:

```python
from <package-name> import <something>
# Implementation example code here
```

### The License Section

The final section MUST be titled `## 📄 License`. It must contain a clear statement identifying the license and a link to the `LICENSE` file in the repository.

```markdown
## 📄 License

This project is licensed under the **MIT License**. See the [LICENSE](./LICENSE) file for details.
```