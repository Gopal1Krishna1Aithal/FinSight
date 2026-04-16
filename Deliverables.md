## **Deliverables**

Participants are expected to submit the following deliverables:

### **1. Backend Service**
Participants should provide a backend service that:

- Accepts bank statements in PDF or image format as input  
- Extracts transaction details such as date, description, debit, credit, and balance  
- Converts the extracted data into a structured spreadsheet format  

**Example Output:**

**Bank Statement:** XYZ Bank

| Date       | Description        | Debit | Credit | Balance | CoA Category     |
|------------|-------------------|-------|--------|---------|------------------|
| 01-02-2026 | Office Supplies   | 200   | –      | 4800    | Office Expenses  |
| 02-02-2026 | Client Payment    | –     | 1500   | 6300    | Revenue          |
| 03-02-2026 | Internet Bill     | 100   | –      | 6200    | Utilities        |

---

### **2. Source Code & Documentation**
Participants must submit the complete source code along with documentation explaining:

- System architecture of the Data Extractor  
- Tools or AI/OCR technologies used for data extraction  
- Steps to install and run the project  
- Example bank statement inputs and generated spreadsheet outputs  

---

### **3. Demo Presentation**
Participants should present:

- A working demo of the bank statement data extraction system  
- Explanation of how transaction data is extracted and mapped to CoA categories  
- Possible future improvements, such as support for multiple bank formats, improved OCR accuracy, and financial analytics dashboards  