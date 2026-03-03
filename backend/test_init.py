import sys
import traceback
sys.path.append('c:/Users/HP/OneDrive/Desktop/AIWorldProject/backend')
try:
    from pipeline.generate_hunyuan import HunyuanGenerator
    print("Imported successfully.")
    h = HunyuanGenerator()
    print("Init successfully.")
except Exception as e:
    with open("c:/Users/HP/OneDrive/Desktop/AIWorldProject/backend/error.log", "w", encoding="utf-8") as f:
        traceback.print_exc(file=f)
    sys.exit(1)
