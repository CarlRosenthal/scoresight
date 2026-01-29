import json
import requests
from text_detection_target import TextDetectionTargetWithResult
from sc_logging import logger
from storage import subscribe_to_data, fetch_data


class UNOAPI:
    def __init__(self, endpoint, field_mapping, field_formatters=None):
        self.endpoint = endpoint
        self.field_mapping = field_mapping
        self.field_formatters = field_formatters or {}
        self.running = False
        self.update_same = fetch_data("scoresight.json", "uno_send_same", False)
        subscribe_to_data("scoresight.json", "uno_send_same", self.set_update_same)
        self.essentials = fetch_data("scoresight.json", "uno_essentials", False)
        subscribe_to_data("scoresight.json", "uno_essentials", self.set_essentials)
        self.uno_essentials_id = fetch_data("scoresight.json", "uno_essentials_id", "")
        subscribe_to_data(
            "scoresight.json", "uno_essentials_id", self.set_uno_essentials_id
        )

    def set_update_same(self, update_same):
        self.update_same = update_same

    def set_essentials(self, essentials):
        self.essentials = essentials

    def set_uno_essentials_id(self, uno_essentials_id):
        self.uno_essentials_id = uno_essentials_id

    def set_field_mapping(self, field_mapping):
        logger.debug(f"Setting UNO field mapping: {field_mapping}")
        self.field_mapping = field_mapping

    def set_field_formatters(self, field_formatters):
        logger.debug(f"Setting UNO field formatters: {field_formatters}")
        self.field_formatters = field_formatters or {}

    def update_uno(self, detection: list[TextDetectionTargetWithResult]):
        if not self.running:
            return

        if not self.field_mapping:
            logger.debug("Field mapping is not set")
            return

        look_in = [TextDetectionTargetWithResult.ResultState.Success]
        if self.update_same:
            look_in.append(TextDetectionTargetWithResult.ResultState.SameNoChange)

        for target in detection:
            if target.result_state in look_in and target.name in self.field_mapping:
                uno_command = self.field_mapping[target.name]
                formatted_value, payload_override = self.format_value(
                    target.name, target.result, uno_command
                )
                self.send_uno_command(uno_command, formatted_value, payload_override)

    def format_value(self, name, value, command):
        formatter = self.field_formatters.get(name)
        if not formatter:
            return value, None

        try:
            if isinstance(formatter, str) and formatter.strip().lower() == "seconds":
                return self.to_seconds(value), None

            if isinstance(formatter, str):
                formatter_text = formatter.strip()
                if formatter_text.lower().startswith("json:"):
                    template = formatter_text[5:].strip()
                    return value, self.render_json_template(template, value, command)
                if formatter_text.startswith("{") and formatter_text.endswith("}"):
                    return value, self.render_json_template(formatter_text, value, command)

            if isinstance(formatter, str):
                return formatter.replace("{value}", str(value)), None
            return value, None
        except Exception as e:
            logger.error(f"Failed to format UNO value for {name}: {e}")
            return value, None

    def render_json_template(self, template, value, command):
        replacements = {
            "{value}": str(value),
            "{value_seconds}": str(self.to_seconds(value)),
            "{value_json}": json.dumps(value),
            "{command}": str(command),
        }
        rendered = template
        for key, replacement in replacements.items():
            rendered = rendered.replace(key, replacement)
        return json.loads(rendered)

    def to_seconds(self, value):
        if isinstance(value, (int, float)):
            return int(value)

        time_str = str(value)
        parts = time_str.split(":")

        try:
            if len(parts) == 3:
                hours, minutes, seconds = [int(part) for part in parts]
                return hours * 3600 + minutes * 60 + seconds
            if len(parts) == 2:
                minutes, seconds = [int(part) for part in parts]
                return minutes * 60 + seconds
            return int(float(time_str))
        except ValueError:
            logger.error(f"Could not parse time value '{value}' as seconds")
            return value

    def send_uno_command(self, command, value, payload_override=None):
        if payload_override is not None:
            payload = payload_override
        elif not self.essentials:
            payload = {"command": command, "value": value}
        else:
            payload = {
                "command": "SetOverlayContentField",
                "value": value,
                "fieldId": command,
                "id": self.uno_essentials_id,
            }

        try:
            response = requests.put(self.endpoint, json=payload)
            if response.status_code != 200:
                logger.error(
                    f"Failed to send data to UNO API, status code: {response.status_code}"
                )
            else:
                logger.debug(f"Successfully sent {command}: {value} to UNO API")

            # Check rate limit headers
            self.check_rate_limits(response.headers)

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send data to UNO API: {e}")

    def check_rate_limits(self, headers):
        rate_limit_headers = [
            "X-Singular-Ratelimit-Burst-Calls",
            "X-Singular-Ratelimit-Daily-Calls",
            "X-Singular-Ratelimit-Burst-Data",
            "X-Singular-Ratelimit-Daily-Data",
        ]

        for header in rate_limit_headers:
            if header in headers:
                limit_info = headers[header]
                logger.debug(f"Rate limit info for {header}: {limit_info}")

                # You can add more sophisticated rate limit handling here if needed
                # For example, pause requests if limits are close to being reached

    def start(self):
        self.running = True

    def stop(self):
        self.running = False
