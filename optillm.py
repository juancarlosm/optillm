import argparse
import logging
import os
import secrets
from flask import Flask, request, jsonify, Response
from openai import OpenAI

# Import approach modules
from mcts import chat_with_mcts
from bon import best_of_n_sampling
from moa import mixture_of_agents
from rto import round_trip_optimization
from z3_solver import Z3SolverSystem
from self_consistency import advanced_self_consistency_approach
from pvg import inference_time_pv_game
from rstar import RStar
from cot_reflection import cot_reflection
from plansearch import plansearch
from leap import leap
from agent import agent_approach

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# OpenAI API configuration
API_KEY = os.environ.get("OPENAI_API_KEY")
default_client = OpenAI(api_key=API_KEY)

# Server configuration
server_config = {
    'approach': 'bon',
    'mcts_simulations': 2,
    'mcts_exploration': 0.2,
    'mcts_depth': 1,
    'best_of_n': 3,
    'model': 'gpt-4o-mini',
    'rstar_max_depth': 3,
    'rstar_num_rollouts': 5,
    'rstar_c': 1.4,
    'n': 1,
    'base_url': '',
    'api_key': '',
    'return_full_response': False,
    'port': 8000,
}

# List of known approaches
known_approaches = ["mcts", "bon", "moa", "rto", "z3", "self_consistency", "pvg", "rstar",
                    "cot_reflection", "plansearch", "leap", "agent"]

# Optional API key configuration to secure the proxy
@app.before_request
def check_api_key():
    if server_config['api_key']:
        if request.path == "/health":
            return

        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Invalid Authorization header. Expected format: 'Authorization: Bearer YOUR_API_KEY'"}), 401

        client_key = auth_header.split('Bearer ', 1)[1].strip()
        if not secrets.compare_digest(client_key, server_config['api_key']):
            return jsonify({"error": "Invalid API key"}), 401

@app.route('/v1/chat/completions', methods=['POST'])
def proxy():
    logger.info('Received request to /v1/chat/completions')
    data = request.get_json()
    logger.debug(f'Request data: {data}')

    messages = data.get('messages', [])
    model = data.get('model', server_config['model'])
    n = data.get('n', server_config['n'])

    system_prompt = next((msg['content'] for msg in messages if msg['role'] == 'system'), "")
    initial_query = next((msg['content'] for msg in messages if msg['role'] == 'user'), "")

    approach = server_config['approach']
    base_url = server_config['base_url']

    if base_url != "":
        client = OpenAI(api_key=API_KEY, base_url=base_url)
    else:
        client = default_client

    # Handle 'auto' approach
    if approach == 'auto':
        for known_approach in known_approaches:
            if model.startswith(f"{known_approach}-"):
                approach = known_approach
                model = model[len(known_approach)+1:]
                break
        else:
            # If no known approach is found in the model name, default to 'bon'
            approach = 'bon'


    logger.info(f'Using approach {approach}, with {model}')

    try:
        if approach == 'mcts':
            final_response = chat_with_mcts(system_prompt, initial_query, client, model, server_config['mcts_simulations'],
                                            server_config['mcts_exploration'], server_config['mcts_depth'])
        elif approach == 'bon':
            final_response = best_of_n_sampling(system_prompt, initial_query, client, model, server_config['best_of_n'])
        elif approach == 'moa':
            final_response = mixture_of_agents(system_prompt, initial_query, client, model)
        elif approach == 'rto':
            final_response = round_trip_optimization(system_prompt, initial_query, client, model)
        elif approach == 'z3':
            z3_solver = Z3SolverSystem(system_prompt, client, model)
            final_response = z3_solver.process_query(initial_query)
        elif approach == "self_consistency":
            final_response = advanced_self_consistency_approach(system_prompt, initial_query, client, model)
        elif approach == "pvg":
            final_response = inference_time_pv_game(system_prompt, initial_query, client, model)
        elif approach == "rstar":
            rstar = RStar(system_prompt, client, model,
                          max_depth=server_config['rstar_max_depth'], num_rollouts=server_config['rstar_num_rollouts'],
                          c=server_config['rstar_c'])
            final_response = rstar.solve(initial_query)
        elif approach == "cot_reflection":
            final_response = cot_reflection(system_prompt, initial_query, client, model, return_full_response=server_config['return_full_response'])
        elif approach == 'plansearch':
            final_response = plansearch(system_prompt, initial_query, client, model, n=n)
        elif approach == 'leap':
            final_response = leap(system_prompt, initial_query, client, model)
        elif approach == 'agent':
            final_response = agent_approach(system_prompt, initial_query, client, model, max_attempts=3)
        else:
            raise ValueError(f"Unknown approach: {approach}")
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return jsonify({"error": str(e)}), 500
   
    if 'stream' in data and data['stream'] == True:
        return Response(_stream(final_response), mimetype='text/event-stream')
    else:
        return final_response.json()

    #return final_response.json(), 200
    #logger.debug(f'API response: {response_data}')
    #return jsonify(response_data), 200

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200


def _stream(response):
    for line in response:
        if 'content' in line['choices'][0]['delta']:
            yield 'data: ' + json.dumps(line.json()) + "\n\n"
    yield 'data: [DONE]\n\n'

def parse_args():
    parser = argparse.ArgumentParser(description="Run LLM inference with various approaches.")

    # Define arguments and their corresponding environment variables
    args_env = [
        ("--api-key", "OPTILLM_API_KEY", str, "", "Optional API key for client authentication to optillm"),
        ("--approach", "OPTILLM_APPROACH", str, "auto", "Inference approach to use", known_approaches),
        ("--simulations", "OPTILLM_SIMULATIONS", int, 2, "Number of MCTS simulations"),
        ("--exploration", "OPTILLM_EXPLORATION", float, 0.2, "Exploration weight for MCTS"),
        ("--depth", "OPTILLM_DEPTH", int, 1, "Simulation depth for MCTS"),
        ("--model", "OPTILLM_MODEL", str, "gpt-4o-mini", "OpenAI model to use"),
        ("--rstar-max-depth", "OPTILLM_RSTAR_MAX_DEPTH", int, 3, "Maximum depth for rStar algorithm"),
        ("--rstar-num-rollouts", "OPTILLM_RSTAR_NUM_ROLLOUTS", int, 5, "Number of rollouts for rStar algorithm"),
        ("--rstar-c", "OPTILLM_RSTAR_C", float, 1.4, "Exploration constant for rStar algorithm"),
        ("--n", "OPTILLM_N", int, 1, "Number of final responses to be returned"),
        ("--return-full-response", "OPTILLM_RETURN_FULL_RESPONSE", bool, False, "Return the full response including the CoT with <thinking> tags"),
        ("--port", "OPTILLM_PORT", int, 8000, "Specify the port to run the proxy"),
    ]

    for arg, env, type_, default, help_text, *extra in args_env:
        env_value = os.environ.get(env)
        if env_value is not None:
            if type_ == bool:
                default = env_value.lower() in ('true', '1', 'yes')
            else:
                default = type_(env_value)
        if extra and extra[0]:  # Check if there are choices for this argument
            parser.add_argument(arg, type=type_, default=default, help=help_text, choices=extra[0])
        else:
            parser.add_argument(arg, type=type_, default=default, help=help_text)

    # Special handling for best_of_n to support both formats
    best_of_n_default = int(os.environ.get("OPTILLM_BEST_OF_N", 3))
    parser.add_argument("--best-of-n", "--best_of_n", dest="best_of_n", type=int, default=best_of_n_default,
                        help="Number of samples for best_of_n approach")

    # Special handling for base_url to support both formats
    base_url_default = os.environ.get("OPTILLM_BASE_URL", "")
    parser.add_argument("--base-url", "--base_url", dest="base_url", type=str, default=base_url_default,
                        help="Base url for OpenAI compatible endpoint")

    args = parser.parse_args()

    # Convert argument names to match server_config keys
    args_dict = vars(args)
    for key in list(args_dict.keys()):
        new_key = key.replace("-", "_")
        if new_key != key:
            args_dict[new_key] = args_dict.pop(key)

    return args


def main():
    global server_config
    args = parse_args()

    # Update server_config with all argument values
    server_config.update(vars(args))

    port = server_config['port']
    logger.info(f"Starting server with approach: {server_config['approach']}")
    server_config_clean = server_config.copy()
    if server_config_clean['api_key']:
        server_config_clean['api_key'] = '[REDACTED]'
    logger.info(f"Server configuration: {server_config_clean}")
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    main()
