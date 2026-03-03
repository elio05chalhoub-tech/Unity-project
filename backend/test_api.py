import requests
import json

api_key = "sukyPhIgk1WTRSSHVKGeY3qwVcG4auiUQwR33xWCywAKLii82vAPkANK68u2"
headers = {"x-api-key": api_key, "Accept": "application/json"}

# The 12225048-6ae6... job returned obfuscated fe9b5515740446f298096037c897c949 and id 15028469
o_id = "fe9b5515740446f298096037c897c949"
i_id = "15028469"

print("Testing Obfuscated ID...")
res1 = requests.get(f"https://backend.blockadelabs.com/api/v1/imagine/requests/{o_id}", headers=headers)
print(res1.status_code, res1.text)

print("\nTesting Integer ID...")
res2 = requests.get(f"https://backend.blockadelabs.com/api/v1/imagine/requests/{i_id}", headers=headers)
print(res2.status_code, res2.text)
