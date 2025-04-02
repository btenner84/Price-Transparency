# NeoMed Atlas: Project Summary

## Project Architecture

This project follows a modern React application architecture with Next.js, leveraging TypeScript for type safety and Tailwind CSS for styling.

### Key Components

1. **Data Processing and Management**
   - Hospital data is pre-processed from Excel to JSON format
   - React Context API manages global state for hospital data
   - Hospital data is grouped by state for efficient access

2. **UI Components**
   - `Header.tsx`: Application header with logo and statistics
   - `USAMap.tsx`: Interactive US map built with react-simple-maps
   - `HospitalList.tsx`: Displays filtered and sortable hospital data
   - `page.tsx`: Main application layout integrating all components

3. **Styling**
   - Custom cyberpunk theme with neon colors and glowing effects
   - Responsive design works on both desktop and mobile
   - Animation effects using Framer Motion for smooth transitions

## Data Flow

1. Hospital data is loaded from `/public/hospital_data.json` at application startup
2. User selects a state on the interactive map
3. Hospital list component displays hospitals for the selected state
4. User can search, filter, and sort hospitals
5. Detailed hospital information is displayed on demand

## Cyberpunk Design Elements

- Neon pink and blue color scheme
- Glowing text and borders
- Grid background pattern
- Angular, geometric design elements
- High contrast dark mode UI

## Future Enhancements

- Add hospital detail pages for more comprehensive information
- Implement hospital comparison features
- Add map markers for individual hospital locations
- Integrate with real-time hospital capacity data
- Add user accounts and favorites functionality 