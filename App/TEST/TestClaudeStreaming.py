import aiohttp
import asyncio
import json

async def stream_claude_response(prompt):
    api_key = 'YOUR_API_KEY'
    url = 'https://api.anthropic.com/v1/messages'
    headers = {
        'Content-Type': 'application/json',
        'X-API-Key': api_key,
        'anthropic-version': '2023-06-01',
    }
    data = {
        'model': 'claude-3-sonnet-20240229',
        'max_tokens': 1000,
        'messages': [{'role': 'user', 'content': prompt}],
        'stream': True
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data, headers=headers) as response:
            async for line in response.content:
                if line:
                    try:
                        event = json.loads(line.decode('utf-8').strip('data: '))
                        if event['type'] == 'content_block_delta':
                            yield event['delta']['text']
                        elif event['type'] == 'message_stop':
                            break
                    except json.JSONDecodeError:
                        pass  # Ignore non-JSON lines

async def main():
    prompt = "Tell me a joke about programming."
    print("Claude's response:")
    async for chunk in stream_claude_response(prompt):
        print(chunk, end='', flush=True)
    print("\nResponse complete.")

if __name__ == "__main__":
    asyncio.run(main())