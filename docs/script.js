const SUPABASE_URL = 'https://hilbbjnnxkitxbptektg.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhpbGJiam5ueGtpdHhicHRla3RnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDgxOTYwNDIsImV4cCI6MjA2Mzc3MjA0Mn0.vk8AJ2pofRAy5y26WQeMYgEFudU1plXnYa6sMFyATFM';

// Ensure Supabase namespace is available (usually it is if CDN script is loaded)
const supabase = (typeof Supabase !== 'undefined') ? Supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY) : null;

async function fetchData() {
    const dataContainer = document.getElementById('data-container');
    if (!supabase) {
        dataContainer.innerHTML = '<p>Supabase client could not be initialized. Check CDN link.</p>';
        console.error('Supabase client is not available. Ensure the Supabase JS library is loaded correctly.');
        return;
    }

    try {
        console.log('Fetching data from Supabase...');
        // Fetch latest 100 items, joining with data_sources to get source name
        // Order by publication_date first (non-nulls), then by scraped_at for items that might have same/null pub date
        let { data: items, error, status, count } = await supabase
            .from('scraped_items')
            .select(`
                title,
                item_url,
                publication_date,
                summary_text,
                scraped_at,
                data_sources ( name ) 
            `)
            .order('publication_date', { ascending: false, nullsFirst: false })
            .order('scraped_at', { ascending: false }) // Secondary sort
            .limit(100);

        console.log('Data fetched:', { items, error, status, count });

        if (error) {
            console.error('Error fetching data:', error);
            dataContainer.innerHTML = `<p>Error loading data. Status: ${status}. Message: ${error.message}. Check console for details.</p>`;
            return;
        }

        if (!items || items.length === 0) {
            dataContainer.innerHTML = '<p>No data breach items found.</p>';
            return;
        }

        // Render data (example: as a list)
        let htmlContent = '<ul>';
        for (const item of items) {
            const publicationDate = item.publication_date ? new Date(item.publication_date).toLocaleDateString() : 'N/A';
            const scrapedDate = item.scraped_at ? new Date(item.scraped_at).toLocaleString() : 'N/A';
            const sourceName = item.data_sources ? item.data_sources.name : (item.source_id ? `Source ID: ${item.source_id}` : 'Unknown Source');
            
            htmlContent += `<li>
                <strong><a href="${item.item_url || '#'}" target="_blank" rel="noopener noreferrer">${item.title || 'No Title'}</a></strong><br>
                Source: ${sourceName}<br>
                Published: ${publicationDate}<br>
                Summary: ${item.summary_text || 'N/A'}<br>
                Scraped at: ${scrapedDate}
            </li><hr>`;
        }
        htmlContent += '</ul>';
        dataContainer.innerHTML = htmlContent;

    } catch (err) {
        console.error('Runtime error during data fetching or rendering:', err);
        dataContainer.innerHTML = '<p>Failed to load data due to a runtime error. Check console.</p>';
    }
}

// Add event listener to run fetchData when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('data-container')) {
        fetchData();
    } else {
        console.error('Data container element not found.');
    }
});
