/**
 * Quick script to test API connectivity
 * Run with: node test-api.js
 */

const API_BASE_URL = process.env.VITE_API_BASE_URL || "https://acme-api-production-e797.up.railway.app";

async function testAPI() {
  console.log(`Testing API at: ${API_BASE_URL}\n`);
  
  try {
    // Test health endpoint
    console.log("1. Testing /health endpoint...");
    const healthResponse = await fetch(`${API_BASE_URL}/health`);
    console.log(`   Status: ${healthResponse.status} ${healthResponse.statusText}`);
    
    if (healthResponse.ok) {
      const healthData = await healthResponse.json();
      console.log(`   Response:`, healthData);
    } else {
      console.log(`   ❌ Health check failed`);
    }
    
    // Test API products endpoint
    console.log("\n2. Testing /api/products endpoint...");
    const productsResponse = await fetch(`${API_BASE_URL}/api/products`);
    console.log(`   Status: ${productsResponse.status} ${productsResponse.statusText}`);
    
    if (productsResponse.ok) {
      const productsData = await productsResponse.json();
      console.log(`   Products count: ${productsData.length || 0}`);
    } else {
      const errorText = await productsResponse.text();
      console.log(`   Error: ${errorText.substring(0, 100)}`);
    }
    
    console.log("\n✅ API is reachable!");
    
  } catch (error) {
    console.error("\n❌ Failed to connect to API:");
    console.error(`   Error: ${error.message}`);
    console.error("\nPossible issues:");
    console.error("   - Railway service is not deployed yet");
    console.error("   - Domain is not generated in Railway dashboard");
    console.error("   - Service is sleeping (Railway free tier)");
    console.error("   - URL is incorrect");
    console.error("\nTo fix:");
    console.error("   1. Go to Railway dashboard → Your API service");
    console.error("   2. Settings → Domains → Generate Domain");
    console.error("   3. Update .env.local with the correct URL");
    process.exit(1);
  }
}

testAPI();

