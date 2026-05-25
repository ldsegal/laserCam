
// Elements
const passwordInput = document.getElementById("input")
const loginContainer = document.getElementById("login")
const appContainer = document.getElementById("app-container")
const video = document.getElementById("stream");
const status = document.getElementById("status");

// SocketIO Connection
var socket = io({
    path: '/socket.io/'
});

// Login Listener
passwordInput.addEventListener("keypress", async function (event) {
    if (event.key === "Enter") {
        const response = await fetch('/check_password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password: passwordInput.value })
        });
        const result = await response.json();
        if (result.success) {
            loginContainer.style.display = "none";
            appContainer.style.display = "block";
            connect();
        } else {
            passwordInput.value = "";
            passwordInput.style.borderColor = "red";
            setTimeout(() => {
                passwordInput.style.borderColor = "";
            }, 500);
        }
    }
});

// WebRTC Video Connection
async function connect() {
    const pc = new RTCPeerConnection();

    pc.ontrack = (e) => {
        status.style.display = "none";
        video.style.display = "block";
        video.srcObject = e.streams[0];
    };
    pc.addTransceiver("video", { direction: "recvonly" });

    try {
        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

        const res = await fetch("/stream/laserCam/whep", {
            method: "POST",
            headers: { "Content-Type": "application/sdp" },
            body: pc.localDescription.sdp
        });

        if (res.status !== 200 && res.status !== 201) {
            throw new Error("Stream not ready");
        }

        const answer = await res.text();
        await pc.setRemoteDescription({ type: "answer", sdp: answer });

    } catch (err) {
        setTimeout(connect, 500);
    }
}

// Function to handle the toggle
function setupToggle(checkboxId, route) {
    const checkbox = document.getElementById(checkboxId);

    checkbox.addEventListener('change', (e) => {
        const isChecked = e.target.checked;
        fetch(route, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ state: isChecked }),
        })
        .then(response => {
            if (response.ok) {
                console.log('Action successful');
            } else {
                console.error('Server returned error:', response.status);
            }
        })
        .catch(error => console.error('Error:', error));
    });
}

// Initialize routes
setupToggle('laser', '/set_laser');
setupToggle('crosshair', '/set_crosshair');

// Joystick
const manager = nipplejs.create({
    zone: document.getElementById('joystick-zone'),
    mode: 'static',
    position: { left: '50%', top: '50%' }, // Center inside the zone
    color: '#0974f1', // Matches your other UI elements
    size: 100,        // Total size of the joystick
    restJoystick: true,
    restOpacity: 0.5  // Fades out slightly when not in use
});
manager.on('move', (evt, data) => {
    socket.emit('joystick_move', { 
        x: data.vector.x, 
        y: data.vector.y 
    });
});

// Set fullscreen on rotate
window.addEventListener("orientationchange", () => {
    if (window.orientation === 90 || window.orientation === -90) {
        const app = document.getElementById("app-container");
        if (app && !document.fullscreenElement) {
            app.requestFullscreen().catch(err => {
                console.log("Fullscreen request failed: " + err.message);
            });
        }
    } else {
        if (document.fullscreenElement) {
            document.exitFullscreen();
        }
    }
});
