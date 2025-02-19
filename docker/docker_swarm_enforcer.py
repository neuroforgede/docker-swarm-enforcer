import docker

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
        print(f"⚠️ {service_name}: Restart delay is already set to {restart_delay}.")

    if update_delay != UPDATE_DELAY and update_delay > 0:
        print(f"⚠️ {service_name}: Update delay is already set to {update_delay}.")

    if restart_delay == RESTART_DELAY and update_delay == UPDATE_DELAY:
        print(f"✅ {service_name}: Already set correctly. Skipping.")
        return    

    print(f"🔄 Updating {service_name}...")

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
        print(f"✅ {service_name}: Updated successfully.")
    except Exception as e:
        print(f"❌ Failed to update {service_name}: {e}")

def main():
    """
    Main function to process all services in the Swarm.
    """
    print("🔍 Checking services in Docker Swarm...")
    
    try:
        services = client.services.list()
        if not services:
            print("⚠️ No services found.")
            return
        
        for service in services:
            update_service(service)

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()