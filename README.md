# Nader-Pletan-Bedside-Health-Monitoring
Bedside Health Monitoring with Wireless Alerts

This project prototypes a bedside monitoring loop using two Raspberry Pi Pico W boards and two laptops. The bedside Pico reads heart-rate, temperature, and tilt at 1 Hz and streams a simple CSV line over USB-serial to the edge laptop. The edge laptop smooths the data, computes lightweight features, runs a scikit-learn model to classify the state (normal/warning/critical), publishes the status to HiveMQ (MQTT over TLS), and when warning or critical—sends a throttled email/SMS alert. A caregiver-station laptop subscribes to the status topic and forwards a tiny command over USB-serial to its paired “indicator” Pico, which drives the traffic-light module (green/yellow/red) and buzzer (off/sporadic/continuous) for immediate visual/audible feedback.

mqtt_utils: a function that allows the user to send data remotely. 

alert_bridge: what the caregiver laptop would run and forwards the information to the display pico and sends warning or critical email to caregiver.

pico_display_server: control the traffic light sensor and buzzer. Also publishes the html giving the display status. 
