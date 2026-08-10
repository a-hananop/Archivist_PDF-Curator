import pdfplumber

def test_extraction():
    pdf = pdfplumber.open("input/PDS_2024_Final_r.pdf")
    page = pdf.pages[40]
    
    settings = {
        "vertical_strategy": "text",
        "horizontal_strategy": "text",
    }
    tables = page.find_tables(settings)
    for t_idx, t in enumerate(tables):
        grid = t.extract()
        print(f"\nTable {t_idx} - Rows: {len(grid)}")
        if grid:
            for i, row in enumerate(grid[:10]):
                filled = sum(1 for c in row if c.strip())
                print(f"  Row {i} (filled {filled}/{len(row)}): {row}")

if __name__ == '__main__':
    test_extraction()
