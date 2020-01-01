import json

i = input('Change ignition to?')
if i == 'on':
    ignition = True
else:
    ignition = False
with open("ignition_state.json", "w") as file:
    json.dump(ignition, file)