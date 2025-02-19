import docker
from threading import Event
import signal
from datetime import datetime
from typing import Any

CHECK_INTERVAL = 60
MAX_FAILS_IN_A_ROW = 3

def print_timed(msg):
    to_print = '{} [{}]: {}'.format(
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'docker_events',
        msg)
    print(to_print)


exit_event = Event()

shutdown: bool = False
def handle_shutdown(signal: Any, frame: Any) -> None:
    print_timed(f"received signal {signal}. shutting down...")
    exit_event.set()

signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)


# Desired settings
# 10 seconds in nanoseconds
RESTART_DELAY = 10 * 1000000000
UPDATE_DELAY = 10 * 1000000000

# Connect to Docker API
client = docker.from_env()

def get_service_settings(service):
    """
    Get the restart and update delay settings for a given service.
    """
    spec = service.attrs["Spec"]
    restart_policy = spec["TaskTemplate"].get("RestartPolicy", {})
    update_config = spec.get("UpdateConfig", {})

    # Get existing settings (if available)
    restart_delay = restart_policy.get("Delay", 0)
    update_delay = update_config.get("Delay", 0)

    return restart_delay, update_delay

def update_service(service):
    """
    Update the service if it does not match the desired settings.
    """
    service_name = service.name
    restart_delay, update_delay = get_service_settings(service)

    if restart_delay != RESTART_DELAY and restart_delay > 0:
        print_timed(f"⚠️ {service_name}: Restart delay is already set to {restart_delay}.")

    if update_delay != UPDATE_DELAY and update_delay > 0:
        print_timed(f"⚠️ {service_name}: Update delay is already set to {update_delay}.")

    if restart_delay == RESTART_DELAY and update_delay == UPDATE_DELAY:
        print_timed(f"✅ {service_name}: Already set correctly. Skipping.")
        return    

    print_timed(f"🔄 Updating {service_name}...")

    # Build the update command with existing config
    update_params = {
        "restart_policy": {
            "Condition": service.attrs["Spec"]["TaskTemplate"].get("RestartPolicy", {}).get("Condition", "any"),
            "Delay": RESTART_DELAY,
            "MaxAttempts": service.attrs["Spec"]["TaskTemplate"].get("RestartPolicy", {}).get("MaxAttempts", 0),
            "Window": service.attrs["Spec"]["TaskTemplate"].get("RestartPolicy", {}).get("Window", 10000000000),
        },
        "update_config": {
            "Parallelism": service.attrs["Spec"].get("UpdateConfig", {}).get("Parallelism", 1),
            "Delay": UPDATE_DELAY,
            "Order": service.attrs["Spec"].get("UpdateConfig", {}).get("Order", "stop-first"),
            "FailureAction": service.attrs["Spec"].get("UpdateConfig", {}).get("FailureAction", "pause"),
            "Monitor": service.attrs["Spec"].get("UpdateConfig", {}).get("Monitor", 5000000000),
            "MaxFailureRatio": service.attrs["Spec"].get("UpdateConfig", {}).get("MaxFailureRatio", 0),
        }
    }

    try:
        service.update(
            restart_policy=update_params["restart_policy"],
            update_config=update_params["update_config"]
        )
        print_timed(f"✅ {service_name}: Updated successfully.")
    except Exception as e:
        print_timed(f"❌ Failed to update {service_name}: {e}")

def main():
    """
    Main function to process all services in the Swarm.
    """

    fails_in_a_row = 0

    while not exit_event.is_set():
        print_timed("🔍 Checking services in Docker Swarm...")
        
        try:
            services = client.services.list()
            if not services:
                print_timed("⚠️ No services found.")
                return
            
            for service in services:
                update_service(service)

            print_timed("🔁 Done checking all services.")

            fails_in_a_row = 0
        except Exception as e:
            print_timed(f"❌ Error: {e}")
            fails_in_a_row += 1
            if fails_in_a_row >= MAX_FAILS_IN_A_ROW:
                print_timed("❌ Too many errors in a row. Exiting...")
                exit_event.set()

        print_timed(f"🕒 Waiting for {CHECK_INTERVAL} seconds...")
        exit_event.wait(CHECK_INTERVAL)

if __name__ == "__main__":
    main()