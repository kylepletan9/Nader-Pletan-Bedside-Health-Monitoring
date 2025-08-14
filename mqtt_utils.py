# mqtt_utils.py

import json
import time
import certifi
import paho.mqtt.client as mqtt

def send_data_line(
        data: dict,
        topic: str,
        broker: str,
        port: int,
        username: str,
        password: str,
        client_id: str = None,
        qos: int = 1
) -> None:
    """
    Publish one JSON-encoded data line to the given MQTT topic over TLS.

    Args:
      data       -- dict of your payload (e.g. {"t":123, "value":42})
      topic      -- topic string (e.g. "home/pico1/raw")
      broker     -- your MQTT hostname (e.g. "2ea6...s1.eu.hivemq.cloud")
      port       -- MQTT-TLS port (usually 8883)
      username   -- MQTT username
      password   -- MQTT password
      client_id  -- optional unique client ID; if None will be auto-generated
      qos        -- MQTT QoS level (0 or 1)
    """
    # generate a unique ID if none provided
    cid = client_id or f"pub-{int(time.time()*1000)}"

    # create & configure client
    client = mqtt.Client(client_id=cid, protocol=mqtt.MQTTv311)
    client.tls_set(ca_certs=certifi.where())      # trust the public CA bundle
    client.username_pw_set(username, password)

    # connect, publish, and tear down
    client.connect(broker, port)
    client.loop_start()
    payload = data if isinstance(data, (str, bytes)) else json.dumps(data)
    client.publish(topic, payload, qos=qos)
    # give it a moment to send
    time.sleep(0.1)
    client.loop_stop()
    client.disconnect()
