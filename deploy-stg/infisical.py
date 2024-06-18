# An extract of RistekCSUI/Infra repository
# This code extract is only for Infisical secrets

import os
import sys
import subprocess
import yaml

from dotenv import load_dotenv
from itertools import chain
from loguru import logger
from pathlib import Path

logger.remove(0)  # Remove default logger
logger.add(
    sys.stderr,
    level="INFO",
    format="{time} | {level} | {module}:{name}:{line} | {message} | {extra}",
    backtrace=True,
)

infisical_filepath = Path("deploy-stg") / "infisical.yml"
if infisical_filepath.is_file():
  with open(infisical_filepath) as infisical_stream, logger.catch(
      exception=(yaml.YAMLError, ValueError)
  ):
      logger.info("Found infisical.yml file")
      logger.info("Reading config from file")
      infisical_config = yaml.safe_load(infisical_stream)
      if (
          infisical_config is None
          or "infisical" not in infisical_config
          or infisical_config["infisical"] is None
      ):
          raise ValueError("empty infisical config")

      infisical = infisical_config["infisical"]
      if "project_id" not in infisical or infisical["project_id"] is None:
          raise ValueError("missing project_id")
      if "env" not in infisical or infisical["env"] is None:
          raise ValueError("missing env")
      if "path" not in infisical or infisical["path"] is None:
          raise ValueError("missing path")

      # Our default value for quoted is false
      if "quoted" not in infisical:
          infisical["quoted"] = False
      elif not isinstance(infisical["quoted"], bool):
          raise ValueError(
              f"expected boolean for quoted, got {type(infisical['quoted'])}"
          )

      project_id = infisical["project_id"]
      env = infisical["env"]
      path = infisical["path"]
      quoted = infisical["quoted"]

      # Load secret as .env file
      logger.info("Loading secrets as .env file")
      subprocess.call(
          f"infisical export --projectId {project_id} --env {env} --path {path}".split(
              " "
          ),
          stdout=open(Path("deploy-stg") / ".env", "w"),
          stderr=sys.stderr,
      )
      logger.info(f"Initial .env file size: {os.stat(Path('deploy-stg') / '.env').st_size}")

      # Strip quotes if not quoted (Infisical exports for .env by default is quoted)
      if not quoted:
          logger.info("Exports are quoted. Running alt logic")
          # Read each variable and strip the quotes
          with open(Path("deploy-stg") / ".env", "r+") as secret_envs:
              quoted_vars = []
              for secret in secret_envs:
                  secret = secret.strip()
                  key, value = secret.split("=", maxsplit=1)
                  if (value[0] == '"' and value[-1] == '"') or (
                      value[0] == "'" and value[-1] == "'"
                  ):
                      value = value[1:-1]
                  quoted_vars.append(f"{key}={value}")

          # Write the contents of quoted vars to the .env file
          with open(Path("deploy-stg") / ".env", "w+") as env_file:
              for var in quoted_vars:
                  env_file.write(var + "\n")
                  
      logger.info(f"Final .env file size: {os.stat(Path('deploy-stg') / '.env').st_size}")