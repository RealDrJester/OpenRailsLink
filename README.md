OpenRailsLink

![alt text](https://img.shields.io/badge/License-MIT-yellow.svg)

![alt text](https://img.shields.io/badge/python-3.8+-blue.svg)

![alt text](https://img.shields.io/badge/status-active-success.svg)

A versatile and powerful control interface for the Open Rails simulator, designed to bridge the gap between your hardware and the virtual cab. OpenRailsLink allows you to connect and map multiple joysticks, yokes, and even the Saitek Pro Flight Switch Panel for an immersive train simulation experience.A workaround until full joystick if implemented into the simulator. 

<img width="1442" height="832" alt="image" src="https://github.com/user-attachments/assets/b7a1f198-eae2-4454-8527-faff3cbb0a86" />

💡 Core Features

   *Multi-Device Support: Connect and use multiple joysticks, gamepads, and other HID devices simultaneously.

   *Saitek Panel Native Support: Out-of-the-box integration with the Logitech/Saitek Pro Flight Switch Panel, including all toggle switches, the rotary dial, and the landing gear lever.

   *Fully Customizable Bindings: An intuitive editor lets you map any physical axis, button, or switch to any Open Rails control, including brakes, throttle, lights, and engine functions.

   *Real-time GUI: The graphical interface provides a complete virtual control panel that mirrors the state of your physical hardware and can be used with a mouse.

   *Live Input Meter: Easily identify which axis or button you are moving with a live feedback meter in the bindings editor.

   *Profile Management: Save and load your complex binding configurations to XML files. Set a default profile to load automatically on startup.

   *Integrated Game Launcher: Configure and launch different Open Rails installations or profiles directly from the application.

⚙️ Requirements

Before you begin, ensure you have the following installed:


     * Python 3.8+

     * An installation of Open Rails (with the web server enabled in the options).

     *  The following Python packages:
      
     * pip install PyQt5 pygame requests websockets lxml hidapi
    
    Or use this method: 
    
        On the terminal prompt run this command:     pip install -r requirements.txt

    

🚀 Installation & First-Time Use

    Clone the Repository:
    
    git clone https://github.com/your-username/OpenRailsLink.git
    cd OpenRailsLink

    
Install Dependencies:
Run the pip command from the Requirements section above.

Connect Hardware:
Plug in all your joysticks and the Saitek Switch Panel before launching the application.

Launch the Application:
      
    *  python OpenRailsLink.py

    
    Initial Setup:

        The application will automatically detect your devices. Check the box next to each device you want to use in the Connected Devices list on the left.

        If your Open Rails web server is running on a port other than 2150, enter the correct port in the Connection box and click Set.

        The status label should change to CONNECTED in green once Open Rails is running and the application connects.

📖 How to Use
Binding Controls

The heart of OpenRailsLink is the bindings editor.

    Click Edit Control Bindings.

    In the dialog, select a control from the list on the left (e.g., "Throttle").

    The panel on the right will show the available bindings for that control.

        For an axis: Move your physical joystick and watch the Live Input Meter to see which axis is active. Click the "Bind" button next to "Axis Binding," then move the axis you want to assign. It will be captured automatically. Check the "Invert" box if the control feels backward.

        For a button/switch: Click the "Bind" button for the desired event ("ON / Press" or "OFF / Release"). Press the button or flip the switch on your hardware to assign it.

    Click Apply & Close to save the new bindings to your current session.

Saving and Loading Profiles

    File > Save Profile As...: Save your current set of bindings to an .xml file for later use.

    File > Load Profile...: Load bindings from a previously saved .xml file.

    File > Set Current as Default Profile: Makes the currently loaded profile open automatically every time you start OpenRailsLink.

The Game Launcher

    Click Edit Launchers... to open the launcher configuration dialog.

    Use the + and - buttons to add or remove launch profiles.

    For each profile (tab), click Browse... to find your OpenRails.exe. The executable's icon will appear on the tab.

    Add any desired command-line arguments (e.g., -skip-intro).

    Close the editor to save. The buttons on the main window will update automatically.

🔧 Configuration Files

OpenRailsLink uses two main types of configuration files:

    config.json: Stores the application's general settings, including the default profile path and all game launcher configurations. This file is managed automatically.

    Profile .xml files: Store the actual control bindings and the list of active devices for a specific configuration. These are created when you use "Save Profile."

🚑 Troubleshooting

    Controller not detected:

        Ensure the controller is plugged in before starting the app.

        Click the Refresh Devices button.

        Make sure your operating system recognizes the device and its drivers are installed.

    "DISCONNECTED" status:

        Ensure Open Rails is running.

        In Open Rails options, verify that the web server is enabled and check its port number.

        Make sure the port in OpenRailsLink matches the one in Open Rails.

        Check your firewall to ensure it isn't blocking local network communication.

    Saitek Panel not working:

        The hidapi library is required. Make sure it's installed.

        On some systems (especially Windows), you may need to run the script with administrator privileges to allow access to HID devices.

    A control is inverted:

        For an axis, use the "Invert" checkbox in the Bindings Editor.

        For a toggle switch that seems backward, try swapping the "ON" and "OFF" event bindings.

Contributing

Contributions are welcome! If you'd like to contribute, please feel free to fork the repository and submit a pull request. For major changes, please open an issue first to discuss what you would like to change.
Code Structure

    OpenRailsLink.py: The main application entry point, containing the QMainWindow and all primary UI logic.

    controls.py: Contains the JoystickManager for Pygame input and the BindingsEditor dialog window.

    hid_manager.py: Handles all low-level communication with the Saitek Pro Flight Switch Panel.

    web_interface.py: Manages all network communication (HTTP and WebSockets) with the Open Rails simulator.

    definitions.py: The master dictionary defining all controllable functions. This acts as the "source of truth" for the application's capabilities.

License

This project is licensed under the MIT License. See the LICENSE file for details.
Acknowledgments

    The Open Rails team for creating an amazing, extensible train simulator.

    The developers of PyQt, Pygame, and the other libraries that make this project possible.
