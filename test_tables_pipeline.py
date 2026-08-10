from extractor.tables import TableExtractor
from pathlib import Path

def test():
    extractor = TableExtractor(Path("input/PDS_2024_Final_r.pdf"))
    tables = extractor.extract_tables_for_page(40) # 0-indexed = page 41
    print(f"Found {len(tables)} table(s)")
    for t in tables:
        print(f"\nTable Rows: {t.num_rows}, Cols: {t.num_cols}")
        if t.rows:
            print("HEADER ROW (Col names):")
            for c in t.rows[0].cells:
                print(f"  [{c.col_index}]: '{c.text}'")
            print("\nFirst data row:")
            for c in t.rows[1].cells:
                print(f"  [{c.col_index}]: '{c.text}'")
            print("\nSecond data row:")
            if len(t.rows) > 2:
                for c in t.rows[2].cells:
                    print(f"  [{c.col_index}]: '{c.text}'")

if __name__ == '__main__':
    test()
