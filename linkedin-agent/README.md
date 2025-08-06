# LinkedIn Agent with MeshAgent

## Overview
This guide explains how to configure LinkedIn authentication for your Agent in MeshAgent to support multiple users posting to their individual LinkedIn accounts.

## LinkedIn Developer App Setup
1. Create LinkedIn Developer App
    - Go to [LinkedIn Developer Portal](https://developer.linkedin.com/)
    - Click "Create app"
    - Fill in required information:
        - App name: Your app name
        - LinkedIn Page: Associate with your company page
        - App logo: Upload a logo
        - Legal agreement: Accept terms

2. Add Necessary Products 
    - Click the "Products Tab"
    - Find "Share on LinkedIn" and click "Request Access" 
    - Find "Sign In with LinkedIn using OpenID Connect" and click "Request Access"


3. Create a Personal Access Token
    - Go to https://www.linkedin.com/developers/tools/oauth you can get here by clicking the Docs and Tools tab in the header then Oauth token tools
    - Click Create a New Access Token
    - Select the app you want to create the token for
    - Select the scopes (openid, profile, w_member_social, and email)
    - Click create. This will prompt you a LinkedIn authorization pop up 
    - Copy and save the generated token

4. Export your environment variables
```bash bash
export LINKEDIN_ACCESS_TOKEN="your_token_from_linkedin_tools"
export LINKEDIN_CLIENT_ID="your_client_id"
export LINKEDIN_CLIENT_SECRET="your_client_secret"
```

## Running the agent
From your terminal activate your virtual environment. Then run the agent and tools

```bash bash
python main.py
```

Next in a seperate tab in your terminal authenticate to meshagent and call the tools and agents into a Room. Make sure you call the tools in first since the agents need the tools to be there to run properly. 

```bash bash
meshagent setup
meshagent call tool --room=linkedin --url=http://localhost:7778/linkedintools --participant-name=linkedintools
meshagent call agent --room=linkedin --url=http://localhost:7778/linkedinagent --participant-name=linkedinagent
meshagent call agent --room=linkedin --url=http://localhost:7778/linkedinmailagent --participant-name=linkedinmailagent
```

Next go to the MeshAgent Studio and send a message to the agent: 
1. [studio.meshagent.com](https://studio.meshagent.com)
2. Click the room ``linkedin``
3. Select the ``linkedinagent`` from the participants tab. 
4. You can now talk with the agent and iterate on the content for your LinkedIn post. Once you are satisifed with the post let the agent know and it will post it to your LinkedIn. 

## Push the Container

docker buildx build --platform linux/amd64 -t your-registry/linkedin-agent:v1 . --push