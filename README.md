# Nader-Pletan-Bedside-Health-Monitoring
Bedside Health Monitoring with Wireless Alerts

This project prototypes a bedside monitoring loop using two Raspberry Pi Pico W boards and two laptops. The bedside Pico reads heart-rate, temperature, and tilt at 1 Hz and streams a simple CSV line over USB-serial to the edge laptop. The edge laptop smooths the data, computes lightweight features, runs a scikit-learn model to classify the state (normal/warning/critical), publishes the status to HiveMQ (MQTT over TLS), and when warning or critical—sends a throttled email/SMS alert. A caregiver-station laptop subscribes to the status topic and forwards a tiny command over USB-serial to its paired “indicator” Pico, which drives the traffic-light module (green/yellow/red) and buzzer (off/sporadic/continuous) for immediate visual/audible feedback.

