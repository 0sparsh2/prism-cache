.PHONY: install test gateway demo-faq demo-faq-dry demo-rag redis-up

install:
	python3.12 -m venv .venv
	.venv/bin/pip install -e ".[dev,gateway,redis]"

test:
	.venv/bin/python -m pytest -q

redis-up:
	docker compose up -d redis

gateway:
	set -a && . ./.env && set +a && .venv/bin/litellm --config gateway/litellm.multi.yaml --port 4000

demo-faq:
	set -a && . ./.env && set +a && .venv/bin/python examples/faq_litellm_gemini.py

demo-faq-dry:
	.venv/bin/python examples/faq_litellm_gemini.py --dry-run

demo-rag:
	set -a && . ./.env && set +a && .venv/bin/python examples/rag_litellm_demo.py --no-llm

demo-tier2:
	.venv/bin/python examples/tier2_faq_demo.py
