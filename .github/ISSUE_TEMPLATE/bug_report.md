name: Bug Report
description: File a bug report
title: "[BUG] "
labels: ["bug"]
body:

- type: dropdown
  id: region
  attributes:
  label: Region
  description: Select the region relevant to this issue
  options: - EU - CA - USA - AUS - China
  validations:
  required: true

- type: dropdown
  id: brand
  attributes:
  label: Brand
  description: Select the vehicle brand
  options: - Hyundai - Kia - Genesis
  validations:
  required: true

- type: textarea
  id: description
  attributes:
  label: Description
  description: Describe the bug in detail
  placeholder: What happened, what you expected, steps to reproduce, etc.
  validations:
  required: true

- type: textarea
  id: logs
  attributes:
  label: Logs / Screenshots
  description: Add logs, screenshots, or error messages if available
  placeholder: Paste logs or drag-and-drop images here
  validations:
  required: false
