import os

with open('frontend/pages/voucher.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

end_idx = 0
for i, line in enumerate(lines):
    if 'class JournalEntryRow(QWidget):' in line:
        end_idx = i
        break

if end_idx == 0:
    print("Could not find JournalEntryRow")
    exit(1)

invoice_code = ''.join(lines[:16] + lines[16:end_idx])
new_voucher_code = ''.join(lines[:16] + ['from frontend.pages.invoice_voucher import InvoiceVoucherDialog\n\n'] + lines[end_idx:])

with open('frontend/pages/invoice_voucher.py', 'w', encoding='utf-8') as f:
    f.write(invoice_code)

with open('frontend/pages/voucher.py', 'w', encoding='utf-8') as f:
    f.write(new_voucher_code)

print("Refactor successful")
