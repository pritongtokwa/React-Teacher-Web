import requests

url = "http://127.0.0.1:5000/submit"

test_data_list = [
    {
        "name": "Test Student 1",
        "class": "Class 1",
        "minigame1": 88,
        "minigame2": 92,
        "minigame3": 75,
        "minigame4": 80
    },
    {
        "name": "Test Student 2",
        "class": "Class 1",
        "minigame1": 70,
        "minigame2": 85,
        "minigame3": 78,
        "minigame4": 90
    },
    {
        "name": "Test Student 3",
        "class": "Class 2",
        "minigame1": 95,
        "minigame2": 89,
        "minigame3": 84,
        "minigame4": 91
    }
]

for test_data in test_data_list:
    response = requests.post(url, json=test_data)
    print("Sent:", test_data["name"])
    print("Status code:", response.status_code)
    print("Response:", response.json())
    print()
