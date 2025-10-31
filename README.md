# 🏅 Nostr Badge Creator Tool


The **Nostr Badge Creator Tool** is a simple yet powerful command-line application for designing and handling badges within the Nostr ecosystem.  
It helps you **create badge definitions**, **award them to other users**, and **manage the acceptance process** — supporting both **creator** and **recipient** perspectives.  

Whether you’re issuing community achievements, personal collectibles, or custom participation tokens — this tool streamlines every step, from creation to verification.

> [!NOTE]
> **Create, award, and manage Nostr badges — fully NIP-58 compliant.**

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
  - [Awarding Badges](#awarding-badges)
  - [Accepting Badges](#accepting-badges)
- [Badge Definitions](#badge-definitions)
  - [Creating Custom Badge Definitions](#creating-custom-badge-definitions)
- [NIP-58 Compliance](#nip-58-compliance)
- [Reference for Nostr Identity Creation (Testing stuff etc)](#reference-for-nostr-identity-creation-testing-stuff-etc)


## Features

- **Badge Definition Creation** - Create NIP-58 compliant badge definitions (kind 30009)
- **Badge Awarding** - Award badges to multiple recipients (kind 8)
- **Badge Acceptance** - Recipients can accept and display badges in their profile (kind 30008)
- **Profile Badge Management** - Merge and manage existing profile badges
- **Multi-Relay Support** - Publish to multiple Nostr relays simultaneously
- **NIP-58 Compliant** - Full compliance with Nostr Improvement Proposal 58

## Prerequisites

- Python 3.8 or higher
- A Nostr private key (nsec format)
- Internet connection for relay communication

## Installation

### 1. Clone the repository
```bash
git clone <your-repo-url>
cd nostr-badges/cli/github
```

### 2. Set up a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate   # On Linux/Mac
# venv\Scripts\activate    # On Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

## Configuration

The tool uses a `config.json` file for configuration. A default configuration is provided with popular Nostr relays:

```json
{
  "relay_urls": [
    "wss://relay.damus.io",
    "wss://nos.lol",
    "wss://nostr.wine",
    "wss://offchain.pub",
    "wss://relay.snort.social",
    "wss://relay.primal.net",
    "wss://relay.nostr.band"
  ]
}
```

## Usage

### Awarding Badges

1. **Start the badge tool:**
   ```bash
   python3 badge_tool.py
   ```

2. **Enter your private key (nsec format):**
   ```
   Enter your private key (nsec): nsec1...
   ```

3. **Select a badge from the available definitions:**
   ```
   📋 Available Badges:
   ------------------
   1) Badge Creator
      ID: badgecreator
      Description: creator of a custom nostr badge
   
   2) Nostr User
      ID: nostruser
      Description: nostr user :)
   ```

4. **Enter recipient pubkeys:**
   ```
   👥 Enter recipient pubkeys (one per line, empty line to finish):
   Recipient: npub1...
   Recipient: npub1...
   Recipient: 
   ```

5. **Confirm and award:**
   ```
   🎯 Ready to award 'Badge Creator' to 2 recipient(s)
   Proceed? (y/n): y
   ```

### Accepting Badges

Recipients can accept badges using the acceptance tool:

1. **Interactive mode:**
   ```bash
   python3 accept_badge.py
   ```

2. **Command line mode:**
   ```bash
   python3 accept_badge.py <nsec> <badge_definition_a_tag> <badge_award_event_id>
   ```

## Badge Definitions

Badge definitions are stored in `badges/definitions/` as JSON files. Each definition follows the NIP-58 format:

```json
{
  "kind": 30009,
  "content": "Badge Name",
  "tags": [
    ["d", "unique-identifier"],
    ["name", "Badge Name"],
    ["description", "Badge description"],
    ["image", "https://example.com/badge.png"],
    ["thumb", "https://example.com/badge-thumb.png"]
  ]
}
```

### Creating Custom Badge Definitions

1. Create a new JSON file in `badges/definitions/`
2. Follow the NIP-58 format above
3. Use a unique identifier for the `d` tag
4. Include name, description, and image URLs as needed

## File Structure

```
Github/
├── badge_creator.py          # Core badge creation logic
├── badge_tool.py            # Main CLI interface
├── accept_badge.py          # Badge acceptance tool
├── recipient_acceptance.py  # Badge acceptance management
├── relay_manager.py         # Relay communication
├── nostr_utils.py          # Nostr utilities
├── config.json             # Configuration file
├── badges/
│   └── definitions/        # Badge definition files
│       ├── badgecreator.json
│       └── nostruser.json
└── badge_backups/          # Backup files (auto-created)
```

## Key Components

### BadgeCreator Class
- Creates badge definitions (kind 30009)
- Awards badges to recipients (kind 8)
- Handles NIP-58 compliance

### BadgeAcceptanceManager Class
- Manages badge acceptance
- Creates profile badges events (kind 30008)
- Handles badge merging and conflicts

### RelayManager Class
- Manages relay connections
- Handles event publishing
- Provides relay status feedback

## Troubleshooting

### Common Issues

1. **"Invalid nsec format"**
   - Ensure your private key starts with `nsec1`
   - Check for typos in the key

2. **"No badge definitions found"**
   - Ensure `badges/definitions/` directory exists
   - Check that JSON files are properly formatted

3. **"Relay connection failed"**
   - Check your internet connection
   - Try different relays in `config.json`
   - Some relays may be temporarily unavailable

4. **"Badge not appearing in profile"**
   - Wait a few minutes for relay propagation
   - Check that the badge was properly accepted
   - Verify the recipient's client supports NIP-58

### Debug Mode

For detailed logging, you can modify the `config.json` to include:
```json
{
  "log_level": "debug"
}
```

## NIP-58 Compliance

This tool is fully compliant with NIP-58 (Badges) specification:
- Badge Definitions (kind 30009)
- Badge Awards (kind 8) 
- Profile Badges (kind 30008)
- Proper tag structure and event signing

For more information about NIP-58, visit: [NIP-58 Specification](https://github.com/nostr-protocol/nips/blob/master/58.md)

## Reference for Nostr Identity Creation (Testing stuff etc)  
https://nostrid.mybuho.de
