from mcp.server.fastmcp import FastMCP

mcp = FastMCP("grammitra-mcp")

@mcp.tool()
def get_nearby_clinics(location: str) -> str:
    """Get list of clinics or medical centers near the location.
    
    Args:
        location: The town or village name.
    """
    loc_lower = location.lower()
    if "primary" in loc_lower or "village" in loc_lower or "rural" in loc_lower or "default" in loc_lower or not loc_lower:
        return (
            "1. Gram Panchayat Primary Health Centre (PHC) - Main Road. Hours: 9 AM - 4 PM. Contact: 080-555-0199\n"
            "2. Government General Hospital - Taluka Headquarter (12 km away). Open 24/7. Contact: 080-555-0100\n"
            "3. Mitra Rural Clinic (Private) - Near Bus Stand. Hours: 8 AM - 8 PM. Contact: 98765-43210"
        )
    return f"Nearby healthcare suggestions for '{location}':\n" \
           f"1. {location} Community Health Centre - Market Road. Hours: 9 AM - 2 PM. Call: 080-555-0211\n" \
           f"2. District Hospital - City Centre (15 km). Open 24/7. Call: 080-555-0200"

@mcp.tool()
def get_disease_info(crop_name: str, disease_name: str) -> str:
    """Get treatment and prevention guidance for crop diseases.
    
    Args:
        crop_name: Name of the crop (e.g. tomato, rice, wheat).
        disease_name: Name of the crop disease or symptom.
    """
    crop = crop_name.lower()
    disease = disease_name.lower()
    
    if "tomato" in crop and ("yellow" in disease or "early blight" in disease or "blight" in disease):
        return (
            "Crop: Tomato | Disease: Early Blight (Alternaria solani)\n"
            "Organic Treatment: Spray Neem oil or copper fungicide. Prune lower leaves to reduce soil splash.\n"
            "Chemical Treatment: Apply Mancozeb or Chlorothalonil according to package instructions.\n"
            "Watering: Avoid overhead watering; use drip irrigation at the base.\n"
            "Prevention: Rotate crops every 2-3 years. Clean tools after usage."
        )
    elif "rice" in crop or "paddy" in crop:
        return (
            "Crop: Rice | Disease: Blast (Magnaporthe oryzae)\n"
            "Organic Treatment: Use silicon fertilizers. Burn or bury crop residues.\n"
            "Chemical Treatment: Tricyclazole or Azoxystrobin spray.\n"
            "Prevention: Avoid excessive nitrogen application. Use resistant seeds."
        )
    return (
        f"General crop guidance for {crop_name} showing '{disease_name}':\n"
        "Organic Treatment: Apply neem-based spray or bio-pesticides. Improve air circulation.\n"
        "Chemical Treatment: Broad-spectrum fungicide or pesticide if symptoms persist.\n"
        "Prevention: Clean tools, rotate crops, keep soil well-drained."
    )

@mcp.tool()
def search_crop_database(crop_name: str) -> str:
    """Get soil, fertilizer, and irrigation guide for a crop.
    
    Args:
        crop_name: Name of the crop (e.g. tomato, cotton, ragi).
    """
    crop = crop_name.lower()
    if "tomato" in crop:
        return (
            "Optimal Conditions for Tomato:\n"
            "- Soil: Well-drained sandy loam, pH 6.0 - 6.8.\n"
            "- Fertilizer: NPK (10-10-10) during planting, switch to low-nitrogen, high-potassium/phosphorus once flowering.\n"
            "- Irrigation: Consistent moisture, 1-1.5 inches per week. Avoid waterlogging."
        )
    elif "cotton" in crop:
        return (
            "Optimal Conditions for Cotton:\n"
            "- Soil: Deep, fertile alluvial or black clayey soil, pH 6.0 - 8.0.\n"
            "- Fertilizer: High nitrogen during early vegetative stage, phosphorus/potassium during bloom.\n"
            "- Irrigation: Heavy watering at flowering/boll development stages."
        )
    return (
        f"Information for crop '{crop_name}':\n"
        "- Soil: Loamy or clayey loam with good drainage, pH 6.0 - 7.0.\n"
        "- Fertilizer: Balanced organic compost or generic NPK fertilizer.\n"
        "- Irrigation: Moderate watering. Allow topsoil to dry slightly between irrigations."
    )

if __name__ == "__main__":
    mcp.run()
