<script lang="ts">
	import type { Token } from 'marked';
	import PlaceResults from './Maps/PlaceResults.svelte';
	import DirectionsDisplay from './Maps/DirectionsDisplay.svelte';
	import PlaceDetails from './Maps/PlaceDetails.svelte';

	export let id: string;
	export let token: Token;

	let mapsData: any = null;
	let error: string | null = null;
	let rawContent: string | null = null;
	let parseAttempts: string[] = [];

	$: if (token?.text) {
		try {
			parseAttempts = [];
			rawContent = token.text;
			
			// Method 1: Parse maps response from HTML-like token
			const htmlMatch = token.text.match(/<maps_response[^>]*>(.*?)<\/maps_response>/s);
			if (htmlMatch) {
				parseAttempts.push('HTML wrapper');
				try {
					mapsData = JSON.parse(htmlMatch[1]);
					error = null;
					validateMapsData(mapsData);
				} catch (e) {
					parseAttempts.push(`HTML parse failed: ${e.message}`);
					mapsData = null;
				}
			}
			
			// Method 2: Try direct JSON parsing if HTML method failed
			if (!mapsData && token.text.trim().startsWith('{') && token.text.trim().endsWith('}')) {
				parseAttempts.push('Direct JSON');
				try {
					mapsData = JSON.parse(token.text.trim());
					error = null;
					validateMapsData(mapsData);
				} catch (e) {
					parseAttempts.push(`Direct JSON parse failed: ${e.message}`);
					mapsData = null;
				}
			}
			
			// Method 3: Look for JSON content within the text
			if (!mapsData) {
				parseAttempts.push('JSON search');
				const jsonMatch = token.text.match(/\{[\s\S]*\}/);
				if (jsonMatch) {
					try {
						mapsData = JSON.parse(jsonMatch[0]);
						error = null;
						validateMapsData(mapsData);
					} catch (e) {
						parseAttempts.push(`JSON search parse failed: ${e.message}`);
						mapsData = null;
					}
				}
			}
			
			// If all parsing methods failed
			if (!mapsData) {
				error = 'Unable to parse maps response from any format';
				console.error('Maps parsing failed. Token content:', token.text.substring(0, 200) + '...');
				console.error('Parse attempts:', parseAttempts);
			}
			
		} catch (e) {
			console.error('Failed to parse maps response:', e);
			mapsData = null;
			error = `Failed to parse maps response: ${e.message}`;
		}
	}

	function validateMapsData(data: any): void {
		if (!data) {
			throw new Error('Empty data object');
		}
		
		if (!data.type || data.type !== 'maps_response') {
			console.warn('Maps data missing type field or invalid type:', data.type);
			// Don't throw error, just warn - some implementations might not include type
		}
		
		if (!data.action) {
			throw new Error('Maps data missing action field');
		}
		
		// Validate action-specific data structures
		switch (data.action) {
			case 'find_places':
				if (!data.data || !Array.isArray(data.data.places)) {
					// Check alternative structure (places directly in data)
					if (!Array.isArray(data.places)) {
						throw new Error('Invalid find_places data structure - missing places array');
					} else {
						// Normalize structure
						data.data = { places: data.places };
						console.log('Normalized find_places data structure');
					}
				}
				break;
			
			case 'get_directions':
				if (!data.data) {
					// Check if route data is directly in the object
					if (data.route || data.directions) {
						data.data = { route: data.route || data.directions };
						console.log('Normalized get_directions data structure');
					} else {
						throw new Error('Invalid get_directions data structure - missing route data');
					}
				}
				break;
			
			case 'place_details':
				if (!data.data) {
					// Check if details are directly in the object
					if (data.place_details || data.details) {
						data.data = { place_details: data.place_details || data.details };
						console.log('Normalized place_details data structure');
					} else {
						throw new Error('Invalid place_details data structure - missing details data');
					}
				}
				break;
			
			default:
				console.warn('Unknown maps action:', data.action);
		}
	}
	
	function getDebugInfo(): string {
		if (!rawContent) return 'No content';
		
		const info = [
			`Content length: ${rawContent.length}`,
			`Parse attempts: ${parseAttempts.length}`,
			`First 100 chars: ${rawContent.substring(0, 100)}...`,
			`Parse attempts: ${parseAttempts.join(', ')}`
		];
		
		return info.join('\n');
	}
</script>

{#if error}
	<div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 my-3">
		<div class="flex items-start gap-3">
			<svg
				class="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5"
				fill="currentColor"
				viewBox="0 0 20 20"
				xmlns="http://www.w3.org/2000/svg"
				aria-hidden="true"
			>
				<path
					fill-rule="evenodd"
					d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-3a1 1 0 00-.867.5 1 1 0 11-1.731-1A3 3 0 0113 8a3.001 3.001 0 01-2 2.83V11a1 1 0 11-2 0v-1a1 1 0 011-1 1 1 0 100-2zm0 8a1 1 0 100-2 1 1 0 000 2z"
					clip-rule="evenodd"
				/>
			</svg>
			<div class="flex-1 min-w-0">
				<h4 class="text-sm font-medium text-red-800 dark:text-red-200 mb-1">
					Maps Display Error
				</h4>
				<p class="text-sm text-red-700 dark:text-red-300 mb-2">
					{error}
				</p>
				<details class="text-xs text-red-600 dark:text-red-400">
					<summary class="cursor-pointer font-medium hover:text-red-800 dark:hover:text-red-200">
						Debug Information
					</summary>
					<pre class="mt-2 whitespace-pre-wrap font-mono bg-red-100 dark:bg-red-900/40 p-2 rounded border">
{getDebugInfo()}
					</pre>
				</details>
			</div>
		</div>
	</div>
{:else if mapsData}
	{#if mapsData.action === 'find_places' && mapsData.data}
		<PlaceResults {id} data={mapsData.data} />
	{:else if mapsData.action === 'get_directions' && mapsData.data}
		<DirectionsDisplay {id} data={mapsData.data} />
	{:else if mapsData.action === 'place_details' && mapsData.data}
		<PlaceDetails {id} data={mapsData.data} />
	{:else}
		<div class="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4 my-3">
			<div class="flex items-start gap-3">
				<svg
					class="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5"
					fill="currentColor"
					viewBox="0 0 20 20"
					xmlns="http://www.w3.org/2000/svg"
					aria-hidden="true"
				>
					<path
						fill-rule="evenodd"
						d="M8.485 3.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 3.495zM10 6a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 6zm0 9a1 1 0 100-2 1 1 0 000 2z"
						clip-rule="evenodd"
					/>
				</svg>
				<div class="flex-1 min-w-0">
					<h4 class="text-sm font-medium text-yellow-800 dark:text-yellow-200 mb-1">
						Unknown Maps Content
					</h4>
					<p class="text-sm text-yellow-700 dark:text-yellow-300 mb-2">
						Received maps data with unrecognized action: <code class="bg-yellow-100 dark:bg-yellow-800/40 px-1 rounded">{mapsData.action || 'undefined'}</code>
					</p>
					<details class="text-xs text-yellow-600 dark:text-yellow-400">
						<summary class="cursor-pointer font-medium hover:text-yellow-800 dark:hover:text-yellow-200">
							Raw Data
						</summary>
						<pre class="mt-2 whitespace-pre-wrap font-mono bg-yellow-100 dark:bg-yellow-900/40 p-2 rounded border max-h-40 overflow-auto">
{JSON.stringify(mapsData, null, 2)}
						</pre>
					</details>
				</div>
			</div>
		</div>
	{/if}
{:else}
	<div class="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4 my-3">
		<div class="flex items-center gap-3">
			<svg
				class="w-5 h-5 text-gray-400"
				fill="currentColor"
				viewBox="0 0 20 20"
				xmlns="http://www.w3.org/2000/svg"
				aria-hidden="true"
			>
				<path
					fill-rule="evenodd"
					d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a.75.75 0 000 1.5h.253a.25.25 0 01.244.304l-.459 2.066A1.75 1.75 0 0010.747 15H11a.75.75 0 000-1.5h-.253a.25.25 0 01-.244-.304l.459-2.066A1.75 1.75 0 009.253 9H9z"
					clip-rule="evenodd"
				/>
			</svg>
			<div class="text-sm text-gray-600 dark:text-gray-400">
				No maps data to display
			</div>
		</div>
	</div>
{/if} 