# Invoice Reset 360

Odoo 19 module that restricts resetting posted invoices or vendor bills to draft once an official QR code has been generated, with granular user-level and time-period-based permission controls.

## Overview

Under tax regulations and electronic invoicing compliance rules (such as ZATCA e-Invoicing in Saudi Arabia), once an invoice is finalized, posted, and its QR code is generated, the document is legally immutable. Modifying it or resetting it to draft is strictly prohibited for standard users. Any adjustments or cancellations must normally be handled via formal **Credit Notes** or **Debit Notes**.

However, administrators may need to grant specific users authorization to reset invoices to draft, either permanently or for a temporary time period (e.g. audit windows, operational corrections).

This module enforces the reset-to-draft restriction while providing an intuitive permission and validity period system for administrators.

## Features

- **Automated Validation on Reset to Draft**: Intercepts `button_draft()` calls and raises a clear `ValidationError` if the invoice is posted with a generated QR code and the user lacks permission.
- **Protection on Direct State Writes**: Also guards programmatic state writes (`write({'state': 'draft'})`).
- **User-Specific Permissions**:
  - **Allow Reset to Draft (QR Invoices)**: Checkbox on user form (`res.users`).
  - **Security Group**: `Allow Reset to Draft (QR Invoices)` (`invoice_reset_360.group_allow_invoice_reset_draft`).
- **Time-Based Validity Period**:
  - **Reset Permission Valid From**: Optional start datetime.
  - **Reset Permission Valid Until**: Optional expiration datetime.
  - If a user's validity period has expired or hasn't started, they are blocked and notified accordingly.
- **Comprehensive QR Code Detection**:
  - Supports `advanced_vat_invoice` module (`qr` binary image field).
  - Supports standard Saudi / ZATCA localization fields (`l10n_sa_qr_code_str`).
- **Informative User Feedback**: Displays an actionable message informing unauthorized users that the invoice is finalized with a QR code and directing them to issue a Credit Note or Debit Note instead.
- **Bilingual Support**: Fully translated into English and Arabic (`i18n/ar.po`).
- **Unit Tests**: Full test suite included in `tests/test_invoice_reset.py` (7 comprehensive test cases).

## How to Grant Permissions to Users

1. Go to **Settings** → **Users & Companies** → **Users**.
2. Open the user to whom you want to grant reset rights.
3. In the **Invoice Reset Rights** tab:
   - Check **Allow Reset to Draft (QR Invoices)**.
   - *(Optional)* Set **Reset Permission Valid From** and **Reset Permission Valid Until** to restrict authorization to a specific timeframe.
4. Save the user record.

## Technical Details

- **Module Name**: `invoice_reset_360`
- **Version**: `19.0.1.1.0`
- **Category**: `Accounting/Accounting`
- **Author**: `Analytix360`
- **Depends**: `account`, `advanced_vat_invoice`
- **License**: `LGPL-3`
