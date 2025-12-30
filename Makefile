# AI Video Agent Makefile
# Provides convenient shortcuts for common tasks

.PHONY: help install run test clean list-models

help:
	@echo "AI Video Agent - Available Commands:"
	@echo ""
	@echo "  make install        - Install dependencies"
	@echo "  make run            - Generate horoscope videos for today"
	@echo "  make run-fast       - Generate videos using fast Veo model"
	@echo "  make run-test       - Generate test videos (cheap models)"
	@echo "  make list-models    - List all available models"
	@echo "  make clean          - Remove output directories"
	@echo "  make test           - Run tests (if available)"
	@echo ""

install:
	pip install -r requirements.txt

run:
	python src/render/veo_horoscope_pipeline.py

run-fast:
	python src/render/veo_horoscope_pipeline.py --veo-model veo-3.1-fast-generate-001

run-test:
	python src/render/veo_horoscope_pipeline.py \
		--veo-model veo-3.1-fast-generate-001 \
		--openai-model gpt-5-nano \
		--out ./out_test

run-premium:
	python src/render/veo_horoscope_pipeline.py \
		--veo-model veo-3.1-generate-001 \
		--openai-model gpt-5.1 \
		--resolution 1080p \
		--out ./out_premium

run-vertical:
	python src/render/veo_horoscope_pipeline.py \
		--aspect 9:16 \
		--veo-model veo-3.1-fast-generate-001

run-landscape:
	python src/render/veo_horoscope_pipeline.py \
		--aspect 16:9 \
		--veo-model veo-3.1-fast-generate-001

run-cyberpunk:
	python src/render/veo_horoscope_pipeline.py \
		--cyberpunk \
		--veo-model veo-3.1-fast-generate-001

list-models:
	python src/render/veo_horoscope_pipeline.py --list-models

horoscopes-only:
	python src/write/horoscope_writer.py

clean:
	rm -rf out_test/ out_real/ out/ out_premium/
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

test:
	@echo "No tests configured yet"
	@echo "Run 'make run-test' to generate test videos instead"
