/**
 * Welcome to Cloudflare Workers! This is your first worker.
 *
 * - Run `npm run dev` in your terminal to start a development server
 * - Open a browser tab at http://localhost:8787/ to see your worker in action
 * - Run `npm run deploy` to publish your worker
 *
 * Bind resources to your worker in `wrangler.jsonc`. After adding bindings, a type definition for the
 * `Env` object can be regenerated with `npm run cf-typegen`.
 *
 * Learn more at https://developers.cloudflare.com/workers/
 */

import jwt from '@tsndr/cloudflare-worker-jwt';

interface Env {
	GOOGLE_SERVICE_ACCOUNT_JSON: string;
	R2_BUCKET_NAME: string;
	WEBHOOK_BASE_URL?: string;
}

interface ProcessPDFRequest {
	pdfUrl: string;
	projectId?: string;
	fileId?: string;
}

interface GoogleServiceAccount {
	type: string;
	project_id: string;
	private_key_id: string;
	private_key: string;
	client_email: string;
	client_id: string;
	auth_uri: string;
	token_uri: string;
	auth_provider_x509_cert_url: string;
	client_x509_cert_url: string;
}

export default {
	async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
		// Handle CORS preflight requests
		if (request.method === 'OPTIONS') {
			return handleCORS();
		}

		// Only allow POST requests
		if (request.method !== 'POST') {
			return createErrorResponse('Method not allowed', 405);
		}

		try {
			// Parse request body
			const requestData: ProcessPDFRequest = await request.json();
			const { pdfUrl, projectId, fileId } = requestData;

			// Validate required fields
			if (!pdfUrl) {
				return createErrorResponse('Missing required field: pdfUrl', 400);
			}

			// Validate PDF URL format
			if (!pdfUrl.startsWith('https://') || !pdfUrl.toLowerCase().endsWith('.pdf')) {
				return createErrorResponse('Invalid PDF URL: must be HTTPS and end with .pdf', 400);
			}

			console.log(`Processing PDF: ${pdfUrl}`);
			if (projectId) console.log(`Project ID: ${projectId}`);
			if (fileId) console.log(`File ID: ${fileId}`);

			// Get Google Cloud access token
			const accessToken = await getGoogleCloudAccessToken(env);
			console.log(`Access token obtained: ${accessToken.substring(0, 20)}...`);

			// Prepare webhook URL
			const webhookUrl = env.WEBHOOK_BASE_URL ? `${env.WEBHOOK_BASE_URL}/api/pdf-webhook` : undefined;

			const workflowUrl = 'https://workflowexecutions.googleapis.com/v1/projects/ladders-doc-pipeline-462921/locations/us-central1/workflows/pdf-processing-workflow/executions';
			console.log(`Calling workflow URL: ${workflowUrl}`);

			const requestBody = {
				argument: JSON.stringify({
					pdfUrl,
					r2Config: {
						bucketName: env.R2_BUCKET_NAME || 'ladders-1'
					},
					projectID: projectId || '',
					projectFileID: fileId || '',
					webhookUrl: webhookUrl || ''
				})
			};
			console.log(`Request body: ${JSON.stringify(requestBody)}`);

			// Call Google Cloud Workflow Executions API
			const workflowResponse = await fetch(workflowUrl, {
				method: 'POST',
				headers: {
					'Authorization': `Bearer ${accessToken}`,
					'Content-Type': 'application/json',
				},
				body: JSON.stringify(requestBody)
			});

			console.log(`Workflow response status: ${workflowResponse.status}`);
			console.log(`Workflow response headers: ${JSON.stringify([...workflowResponse.headers.entries()])}`);

			if (!workflowResponse.ok) {
				const errorText = await workflowResponse.text();
				console.error('Workflow API error response:', errorText);
				return createErrorResponse(`Workflow API error: ${workflowResponse.status} - ${errorText}`, 500);
			}

			const workflowResult: any = await workflowResponse.json();
			const executionId = workflowResult.name.split('/').pop();

			console.log(`Workflow execution started: ${executionId}`);

			// Return success response
			return createSuccessResponse({
				success: true,
				executionId,
				status: 'processing_started',
				message: 'PDF processing has been initiated successfully'
			});

		} catch (error) {
			console.error('PDF processing error:', error);
			return createErrorResponse(
				error instanceof Error ? error.message : 'Unknown error occurred',
				500
			);
		}
	},
};

async function getGoogleCloudAccessToken(env: Env): Promise<string> {
	try {
		// Parse service account JSON
		const serviceAccount: GoogleServiceAccount = JSON.parse(env.GOOGLE_SERVICE_ACCOUNT_JSON);

		// Create JWT payload
		const now = Math.floor(Date.now() / 1000);
		const payload = {
			iss: serviceAccount.client_email,
			scope: 'https://www.googleapis.com/auth/cloud-platform',
			aud: 'https://oauth2.googleapis.com/token',
			exp: now + 3600, // 1 hour
			iat: now
		};

		// Sign JWT
		const token = await jwt.sign(payload, serviceAccount.private_key, { algorithm: 'RS256' });

		// Exchange JWT for access token
		const tokenResponse = await fetch('https://oauth2.googleapis.com/token', {
			method: 'POST',
			headers: {
				'Content-Type': 'application/x-www-form-urlencoded'
			},
			body: new URLSearchParams({
				grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer',
				assertion: token
			})
		});

		if (!tokenResponse.ok) {
			const errorText = await tokenResponse.text();
			throw new Error(`Token exchange failed: ${errorText}`);
		}

		const tokenData: any = await tokenResponse.json();
		return tokenData.access_token;

	} catch (error) {
		console.error('Error getting access token:', error);
		throw new Error('Failed to authenticate with Google Cloud');
	}
}

function handleCORS(): Response {
	return new Response(null, {
		status: 204,
		headers: {
			'Access-Control-Allow-Origin': '*',
			'Access-Control-Allow-Methods': 'POST, OPTIONS',
			'Access-Control-Allow-Headers': 'Content-Type, Authorization',
			'Access-Control-Max-Age': '86400', // 24 hours
		},
	});
}

function createSuccessResponse(data: any): Response {
	return new Response(JSON.stringify(data), {
		status: 200,
		headers: {
			'Content-Type': 'application/json',
			'Access-Control-Allow-Origin': '*',
			'Access-Control-Allow-Methods': 'POST, OPTIONS',
			'Access-Control-Allow-Headers': 'Content-Type, Authorization',
		},
	});
}

function createErrorResponse(message: string, status: number): Response {
	return new Response(
		JSON.stringify({
			success: false,
			error: message,
			timestamp: new Date().toISOString()
		}),
		{
			status,
			headers: {
				'Content-Type': 'application/json',
				'Access-Control-Allow-Origin': '*',
				'Access-Control-Allow-Methods': 'POST, OPTIONS',
				'Access-Control-Allow-Headers': 'Content-Type, Authorization',
			},
		}
	);
}
