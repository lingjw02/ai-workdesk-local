# Emilia companion

Open **Companion** in the EMILIA LAB sidebar. The transparent pet stays across app pages. Click her to switch modes, open her room, or hide her. Drag to reposition; focused arrow keys also move her. Show a hidden pet again from her room.

**Close room** returns to the page you came from; it leaves the floating pet available.

## Emilia and Main Brain

Choose **Chat with Emilia** in her room or pet menu. It opens the active Main Brain conversation, including its saved messages. **Open full conversation** continues the same conversation in the workspace chat. Both interfaces use `/api/chat`, the same configured model router, and Main Brain's global memory. There is no separate companion model or memory database.

Simple chat now supplies recent conversation history and shared global memory to the model, with a shared Emilia/Main Brain identity. Context is bounded to 24 recent messages and a bounded memory excerpt. Conversations are persisted normally; this does not automatically promote every sentence into permanent global memory. Existing explicit Vault memory saving remains available and its global-memory write was corrected.

Screen captures and visual observations are not added to shared model context. Local-only awareness remains independent of the configured text-chat provider. Browser verification mocks model replies; it verifies the shared conversation ID, persisted-message display and navigation, without making a live provider call.

## Modes and care

- Roaming: walking frames, tea, ice magic, phone, greeting and sleeping poses. Time of day influences idle choices. Reduced motion disables autonomous walking. Pause roaming keeps her in place.
- Bongo: left/right key groups and mouse-down update the matching hand immediately. Key-up, mouse-up and window blur release them. Only this app receives input; there is no OS-wide keyboard hook or stored typing history. Settings and private fields do not drive Bongo.
- Care: tea, greeting and magic earn bounded XP. Interactions share a 30-second reward cooldown; tea has a 60-second cooldown. Maximum 120 XP/day, without penalties for absence. Progress, outfit and position persist in this browser's local storage.
- The room has chair, desk and crystal-shelf anchors. Select one to invite Emilia over; idle activities can also use visible anchors.

## Wardrobe

The room always shows the model. Zooming switches to normal proportions. Tops, bottoms, socks, shoes and headwear compose independently over the same character. Chibi and normal forms have separate fitting anchors. Original, casual, ice queen, kimono and maid pieces are available; summer sandals and hat are available.

`public/assets/pet/manifest.json` inventories all six original `skins` / `skins_full` themes and maps the reconstructed accessory atlas fragments to categories and coordinates. Source artwork in the old desktop_pet project is unchanged. Existing band-cut assets had damaged fabric and hair fragments, so the usable clothing was reconstructed with the native image tool.

Current art limits:

- Custom outfits use the standing pose. Bongo and expressive animations use the original outfit.
- The modest lilac base garment is baked into the character base. Swim top/bottom pieces are catalogued but not offered until a compatible base garment exists.
- Glasses and earrings were absent from the supplied outfit assets, so their categories have no selectable items.
- The generated cutouts can still show small edge artifacts, and some combinations need finer fitting. They are modular 2D pieces, not a skeletal clothing rig.
- Stockings now map each leg's texture to the actual character silhouette in both forms, replacing rectangular placement that exposed skin along the calves.
- Stockings extend through the foot silhouette so base slippers do not show through when no shoes are selected. Ice-queen and kimono hair ornaments have their own proportions and temple anchors instead of inheriting the long original ribbon's dimensions.

The preview, furniture toolbar and caption scroll as one sticky group on sufficiently tall desktop windows. Furniture buttons remain below the preview in equal-width columns. On phones and short windows the group scrolls normally. Inviting Emilia to furniture places her above the toolbar without covering its controls.

## Local-only visual awareness

Start a local vision-capable service that exposes OpenAI-compatible `/v1/models` and `/v1/chat/completions`. In **Companion → Local awareness**, enter its loopback endpoint and exact model ID, then select **Save and test**. The default endpoint is `http://127.0.0.1:11434/v1`. The app does not install or start a model.

Enable **Let Emilia see this workspace**. Awareness captures changed visible app content at most once every ten seconds, with one request in flight. It stays off on reload. Settings, the companion configuration page, input fields, private elements, embedded media and the pet itself are excluded. Some DOM effects are not reproduced by the capture library.

Frames stay in memory, pass through the app's local route to the selected loopback model, and are never written to disk by the companion. The external local model service has its own logging settings. There is no cloud fallback. Numeric loopback endpoints and localhost are accepted; redirects, proxies, remote clients and external origins are rejected. Turning awareness off aborts the browser request and discards late results; local inference already started may finish server-side before its 20-second timeout.

Observations are plain text. Screen content cannot trigger tools or app actions. Config persistence contains only endpoint and model ID in `data/companion_vision.json`.

## Validation

Run:

```
node --test tests/pet-state.test.cjs tests/pet-awareness.test.cjs tests/dashboard.test.cjs
venv\Scripts\python.exe -m unittest discover -s tests -p test_companion_vision.py
```

Browser checks in `.codex-review/pet-browser.cjs`, `pet-interactions.cjs`, and `pet-awareness-browser.cjs` cover desktop/mobile, transparent assets, real Bongo inputs, drag versus click, saved progress/outfits/position, zoom, opt-in reset, changed-frame sampling and excluded views. They use local Edge through the installed Playwright runtime. Vision responses are mocked; no running local vision model was available for actual inference validation.
