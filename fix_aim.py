import re

with open("backend/src/spatial/aim.py", "r") as f:
    text = f.read()

text = text.replace('def is_ref_poi_id(poi_id: str) -> bool:\n    return bool(_REF_POI_ID_RE.fullmatch(poi_id))', 
'''def is_ref_poi_id(poi_id: str) -> bool:
    if poi_id == "table_center":
        return True
    return bool(_REF_POI_ID_RE.fullmatch(poi_id))''')

with open("backend/src/spatial/aim.py", "w") as f:
    f.write(text)
