This is the help and instructions file for the Open Rails Advanced Controller.

--- First Time Setup ---
1. Connect all your joystick/controller devices.
2. Launch this application (OpenRailsLink.py).
3. Select the correct Open Rails port if it's not 2150 and click "Set".
4. Check the box next to each device you want to use in the "Connected Devices" list.

--- Binding Controls ---
1. Click "Edit Control Bindings".
2. Select a control from the list on the left (e.g., "Throttle").
3. The panel on the right will update. To see which axis to bind, move your physical joystick and watch the "Live Input Meter".
4. Click the "Bind Axis" button (it will say "Listening...").
5. Move the joystick axis you want to assign. It will be captured automatically.
6. Check the "Invert Axis" box if the control feels backward.
7. You can also bind "Increase/Decrease" to buttons for fine-tuning.
8. Click "Apply & Close" to save your new bindings.

--- Saving Profiles ---
1. Go to File -> Save Profile As... to save your bindings to an .xml file.
2. You can set a profile to load every time by going to File -> Set Current as Default Profile.

--- Game Launcher ---
1. Click the "Edit Launchers..." button to open the editor.
2. Use the (+) button to add a new launch configuration tab.
3. Use the "Browse..." button to find your OpenRails.exe. The icon should appear on the tab. (Great for many of the OR variants)
4. You can add any command-line arguments (like -skip-intro) in the arguments field.
5. Drag and drop the tabs to reorder them. This changes the order of the launch buttons on the main screen.
6. Close the editor. Your launcher tabs are saved automatically when you close the main program.
7. You can change the order of the icons by moving the tabs in the Launcher editor. 


--- Known bugs/issues ---

1. CP_Handle will not move the slider, but information is being sent.
2. Bell for some reason doesn't work or is sent. Same problem happens in the javascript version of the game.
3. "Instrument Lights" sends Pantograph 1. 
4. Can't seem to find a way to add other joysticks, like Thrustmaster MFD1. But At least Saitek Switch Panel works. 
5. I do not own other Saitek panels, so I cannot add or test them. This will be up to you. 