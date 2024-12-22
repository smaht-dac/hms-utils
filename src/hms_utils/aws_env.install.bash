HMS_AWS_ENV_SHELL_SCRIPT_LOCAL_FILE=~/.hms_aws_env.sh
HMS_AWS_ENV_PYTHON_SCRIPT_LOCAL_FILE=~/.hms_aws_env.py
curl 'https://raw.githubusercontent.com/smaht-dac/hms-utils/refs/heads/main/src/hms_utils/aws_env.sh' > $HMS_AWS_ENV_SHELL_SCRIPT_LOCAL_FILE
curl 'https://raw.githubusercontent.com/smaht-dac/hms-utils/refs/heads/main/src/hms_utils/aws_env.py' > $HMS_AWS_ENV_PYTHON_SCRIPT_LOCAL_FILE
chmod a+x $HMS_AWS_ENV_SHELL_SCRIPT_LOCAL_FILE
export FOO=HOO
