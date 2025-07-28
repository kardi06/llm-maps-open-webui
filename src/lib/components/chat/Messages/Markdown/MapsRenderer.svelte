<script lang="ts">
	import type { Token } from 'marked';
	import PlaceResults from './Maps/PlaceResults.svelte';
	import DirectionsDisplay from './Maps/DirectionsDisplay.svelte';
	import PlaceDetails from './Maps/PlaceDetails.svelte';

	export let id: string;
	export let token: Token;

	let mapsData: any = null;
	let error: string | null = null;

	$: if (token?.text) {
		try {
			// Parse maps response from HTML-like token
			const match = token.text.match(/<maps_response[^>]*>(.*?)<\/maps_response>/s);
			if (match) {
				mapsData = JSON.parse(match[1]);
				error = null;
			} else {
				// Fallback: try to parse if the token text is direct JSON
				if (token.text.startsWith('{') && token.text.endsWith('}')) {
					mapsData = JSON.parse(token.text);
					error = null;
				} else {
					mapsData = null;
					error = null;
				}
			}
		} catch (e) {
			console.error('Failed to parse maps response:', e);
			mapsData = null;
			error = 'Failed to parse maps response';
		}
	}
</script>

{#if error}
	<div class="text-red-500 text-sm p-2 bg-red-50 dark:bg-red-900/20 rounded">
		{error}
	</div>
{:else if mapsData && mapsData.type === 'maps_response'}
	{#if mapsData.action === 'find_places' && mapsData.data}
		<PlaceResults {id} data={mapsData.data} />
	{:else if mapsData.action === 'get_directions' && mapsData.data}
		<DirectionsDisplay {id} data={mapsData.data} />
	{:else if mapsData.action === 'place_details' && mapsData.data}
		<PlaceDetails {id} data={mapsData.data} />
	{:else}
		<div class="text-gray-500 text-sm p-2">
			Unknown maps action: {mapsData.action}
		</div>
	{/if}
{/if} 