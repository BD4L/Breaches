# Breach Dashboard Frontend Plan

## 🎯 Project Overview
Building a comprehensive breach data dashboard that leverages our rich 44-field database schema with 2,129+ breach records from 37+ sources.

## 📊 Current Data Assets
- **2,129+ breach records** across government, state AG, news, and specialized sources
- **37+ data sources** with rich categorization (State AG, News Feed, Government Portal, etc.)
- **Rich schema** with incident details, document links, affected counts, data types compromised
- **Active scrapers** continuously collecting new breach data

## 🏗️ Architecture Stack
- **Framework**: Astro + React (SSG with client-side interactivity)
- **UI Library**: shadcn/ui + Tailwind CSS
- **Data Table**: TanStack Table v8
- **Database**: Supabase (existing schema)
- **Authentication**: Supabase Auth
- **Deployment**: GitHub Pages (static site)

## 📋 Core Features

### 1. **Main Dashboard**
- **Enhanced data table** using `v_breach_dashboard` view
- **Advanced filtering** by source type, data types, date ranges
- **Real-time search** across organization names and breach details
- **Export functionality** for filtered results
- **Responsive design** for mobile/tablet viewing

### 2. **Rich Breach Details**
- **Expandable rows** showing full incident details
- **Document links** to official notices and reports
- **Timeline visualization** (discovery → disclosure → containment)
- **Data types compromised** with visual indicators
- **Source attribution** with links back to original portals

### 3. **User Preferences & Alerts**
- **Alert configuration** with threshold, source, and keyword settings
- **Email notification** preferences
- **Saved filter** presets
- **Dashboard customization** options

### 4. **AI Research Integration**
- **Deep research** button for AI-powered breach analysis
- **Research job** status tracking
- **Generated reports** viewing and download

## 🎨 UI/UX Design

### Color Scheme
- **Primary**: Blue (#2563eb) - trust and security
- **Secondary**: Slate (#64748b) - professional
- **Accent**: Orange (#ea580c) - alerts and warnings
- **Success**: Green (#16a34a) - positive actions
- **Destructive**: Red (#dc2626) - critical breaches

### Layout Structure
```
┌─────────────────────────────────────────────────────┐
│ Header: Logo | Navigation | User Menu               │
├─────────────────────────────────────────────────────┤
│ Filters: Source Types | Data Types | Date Range     │
├─────────────────────────────────────────────────────┤
│ Stats: Total Breaches | Affected | Recent Activity  │
├─────────────────────────────────────────────────────┤
│                                                     │
│ Main Data Table with Expandable Rows               │
│                                                     │
├─────────────────────────────────────────────────────┤
│ Pagination | Export | Bulk Actions                 │
└─────────────────────────────────────────────────────┘
```

## 📁 File Structure
```
frontend/
├── src/
│   ├── components/
│   │   ├── ui/              # shadcn/ui components
│   │   ├── dashboard/       # Dashboard-specific components
│   │   ├── filters/         # Filter components
│   │   └── breach/          # Breach detail components
│   ├── lib/
│   │   ├── supabase.ts      # Supabase client
│   │   ├── types.ts         # TypeScript types
│   │   └── utils.ts         # Utility functions
│   ├── pages/
│   │   ├── index.astro      # Main dashboard
│   │   ├── breach/[id].astro # Breach detail page
│   │   └── settings.astro   # User preferences
│   └── layouts/
│       └── Layout.astro     # Base layout
├── public/
├── package.json
└── astro.config.mjs
```

## 🔧 Implementation Phases

### Phase 1: Foundation ✅ COMPLETED
- [x] Set up Astro project with TypeScript
- [x] Install and configure dependencies (React, TanStack Table, Tailwind, Supabase)
- [x] Set up Supabase client and types
- [x] Create base layout and routing
- [x] Create UI component library (Button, Input, Badge)

### Phase 2: Core Dashboard ✅ COMPLETED
- [x] Build main data table with TanStack Table
- [x] Implement basic filtering and search
- [x] Add source type and data type filters
- [x] Create breach detail expandable rows
- [x] Add responsive design
- [x] Implement pagination and sorting

### Phase 3: Advanced Features (In Progress)
- [ ] Set up environment variables and Supabase connection
- [ ] Test dashboard with real data
- [ ] Implement user preferences system
- [ ] Add alert configuration UI
- [ ] Build AI research integration
- [ ] Add export functionality
- [ ] Implement saved filters

### Phase 4: Polish & Deploy (Upcoming)
- [ ] Add loading states and error handling
- [ ] Implement dark mode toggle
- [ ] Add analytics and monitoring
- [ ] Performance optimization
- [ ] Deploy to GitHub Pages

## 🔍 Key Components

### BreachTable Component
- Uses TanStack Table for performance
- Server-side filtering via Supabase
- Expandable rows for detailed view
- Column sorting and resizing
- Bulk selection capabilities

### FilterPanel Component
- Source type chips with counts
- Data type multi-select
- Date range picker with presets
- Affected individuals slider
- Keyword search with suggestions

### BreachDetail Component
- Rich incident information display
- Document links and previews
- Timeline visualization
- Data types compromised indicators
- Source attribution

### UserPreferences Component
- Alert threshold configuration
- Source and keyword preferences
- Email notification settings
- Saved filter management

## 📊 Data Integration

### Supabase Queries
```typescript
// Main dashboard query
const { data: breaches } = await supabase
  .from('v_breach_dashboard')
  .select('*')
  .eq('source_type', selectedType)
  .gte('affected_individuals', minAffected)
  .order('publication_date', { ascending: false })
  .range(offset, offset + limit)

// Filter options
const { data: sourceTypes } = await supabase
  .from('data_sources')
  .select('type')
  .distinct()
```

### TypeScript Types
```typescript
interface BreachRecord {
  id: number
  organization_name: string
  breach_date: string | null
  affected_individuals: number | null
  what_was_leaked: string | null
  data_types_compromised: string[] | null
  source_name: string
  source_type: string
  notice_document_url: string | null
  // ... other fields
}
```

## 🚀 Current Status & Next Steps

### ✅ Completed
1. **Project Structure**: Astro + React + TypeScript setup complete
2. **UI Components**: Button, Input, Badge, Layout components built
3. **Core Dashboard**: BreachTable with TanStack Table, sorting, pagination
4. **Filtering System**: FilterPanel with source types, search, affected thresholds
5. **Breach Details**: Expandable rows with rich incident information
6. **Responsive Design**: Mobile-friendly layout with Tailwind CSS

### 🔄 Next Steps
1. **Environment Setup**: Configure Supabase connection with environment variables
2. **Data Integration**: Test dashboard with live breach data from database
3. **Enhanced Features**: Add user preferences, alerts, and AI research integration
4. **Deployment**: Set up GitHub Pages deployment with proper base path

### 📋 To Test the Dashboard
1. Copy `.env.example` to `.env` and add your Supabase credentials
2. Run `npm run dev` to start the development server
3. Navigate to `http://localhost:4321` to view the dashboard

---

*This plan is actively maintained and updated as we progress through implementation.*
