import os
import csv
import re
import logging
import traceback

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, NoSuchElementException

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

driver = webdriver.Chrome()
driver.set_window_size(2400, 1800)
wait = WebDriverWait(driver, 10)

def from_percentage_to_number(percentage):
    try:
        return round(float(percentage.rstrip('%')) * 0.01, 3)
    except ValueError:
        raise ValueError(f"Could not convert percentage to number: {percentage}")    

def find_min_max_number_in_string(string):
    match = re.search(r"(\d+)\s*-\s*(\d+)\s*kg/m³", string)
    if match:
        min_value = match.group(1)
        max_value = match.group(2)
    else:
        min_value = find_number_in_string(string)
        max_value = min_value
    return (min_value, max_value)

def find_number_in_string(string):
    numbers = re.findall(r"\d+(?:\.\d+)?", string)
    if len(numbers) == 1:
        return numbers[0]
    elif len(numbers) > 1:
        raise ValueError(f"Multiple numbers found in string: {string}")
    raise ValueError(f"No number found in string: {string}")

def format_functional_unit(functional_unit):
    if "m²" in functional_unit or "m2" in functional_unit:
        return "sqm"
    if "m³" in functional_unit or "m3" in functional_unit:
        return "cbm"
    if "m" in functional_unit:
        return "m"
    if "kg" in functional_unit:
        return "kg"
    if "piece" in functional_unit:
        return "piece"
    if "kW" in functional_unit:
        return "kW"
    logging.warning(f"Unknown functional unit: {functional_unit}")
    return functional_unit

def safe_click(element):
    try:
        element.click()
    except (StaleElementReferenceException, NoSuchElementException) as e:
        logging.error(f"Error clicking element: {e}")
        traceback.print_exc()

def wait_for_element(selector, by=By.CSS_SELECTOR):
    return wait.until(EC.presence_of_element_located((by, selector)))

def scroll_to_element(parent, child):
    driver.execute_script("""
        const parent = arguments[0];
        const child = arguments[1];
        parent.scrollTop = child.offsetTop - parent.offsetTop;
    """, parent, child)

def login():
    logging.info("Logging in...")
    driver.get("https://www.totem-building.be")
    
    wait_for_element("//*[@id='app']/div[1]/div[2]/div[2]/div[2]/div", By.XPATH).click()

    email_input = wait_for_element("//*[@id='app']/div[1]/div[2]/div[2]/div[2]/div/span[1]/span[2]/input", By.XPATH)
    password_input = wait_for_element("//*[@id='app']/div[1]/div[2]/div[2]/div[2]/div/span[2]/span[2]/input", By.XPATH)
    login_button = wait_for_element("//*[@id='app']/div[1]/div[2]/div[2]/div[3]/div[1]/div[2]", By.XPATH)
    
    email_input.send_keys(os.getenv("TOTEM_USERNAME"))
    password_input.send_keys(os.getenv("TOTEM_PASSWORD"))
    safe_click(login_button)

    wait_for_element("#app > div.home-page > div.main-content")
    logging.info("Successfully logged in")

def scrape_elements():
    logging.info("Scraping elements...")
    driver.get("https://www.totem-building.be/user.library.xhtml?l=ELEMENTTYPE")
    
    elements_base_selector = "#app > div.library > div.libraryDetail.ELEMENTTYPE > div > div.south-part"
    elements_list_selector = f"{elements_base_selector} > div.filterAndList > div.listArea > div.listWrapper > div.list"
    elements_selector = f"{elements_list_selector} > div"
    element_details_selector = f"{elements_base_selector} > div.selectionDetails > div.etLibraryObject"

    wait_for_element(f"{element_details_selector} > div.propertiesAndImage > div > span.property.name > span.value")

    elements_list = driver.find_element(By.CSS_SELECTOR, elements_list_selector)
    elements = driver.find_elements(By.CSS_SELECTOR, elements_selector)

    logging.info(driver.find_element(By.CSS_SELECTOR, f"{elements_base_selector} > div.filterAndList > div.listArea > div.listAreaTitle > span.totalSize").text)
    logging.info(f"Elements in list: {len(elements)}")

    with open('elements.csv', mode='w', newline='') as file:
        writer = csv.writer(file, delimiter=';')
        writer.writerow(['Element Name', 'Element U-Value', 'Layer', 'Composition', 'Ratio', 'Component Name', 'Application', 'Lifetime', 'Thickness'])

        for i in range(len(elements)):
            try:
                # Re-fetch to avoid StaleElementReferenceException
                elements = driver.find_elements(By.CSS_SELECTOR, elements_selector)
                element = elements[i]

                # Update element details
                safe_click(element)
                scroll_to_element(elements_list, element)

                # Scrape
                element_name = wait_for_element(f"{element_details_selector} > div.propertiesAndImage > div > span.property.name > span.value").text                
                try:
                    element_u_value = driver.find_element(By.CSS_SELECTOR, f"{element_details_selector} > div.propertiesAndImage > div > span.property.uvalue > span.value")
                    element_u_value = find_number_in_string(element_u_value.text)
                except:
                    # logging.info(f"No U-value found for element '{element_name}'")
                    element_u_value = None

                components = driver.find_elements(By.CSS_SELECTOR, f"{element_details_selector} > div.layerTable > div.layerTableScroll > div.rowGroups > div.rows > div.layerWrapper")
                for component in components:
                    try:
                        component_classes = component.get_attribute("class")
                        if "homogeneous" in component_classes:
                            layer = component.find_element(By.CSS_SELECTOR, "div > span.identifier").text
                            composition = "a"
                            ratio = 1
                            name = component.find_element(By.CSS_SELECTOR, "div > span.name").text
                            application = component.find_element(By.CSS_SELECTOR, "div > span.category").text
                            lifetime = find_number_in_string(component.find_element(By.CSS_SELECTOR, "div > div.properties > div.lifetime").text)
                            try:
                                thickness = find_number_in_string(component.find_element(By.CSS_SELECTOR, "div > div.properties > div.param1").text)
                            except:
                                # logging.info(f"No thickness found for:\n  element '{element_name}'\n  component '{name}' - '{application}'")
                                thickness = None

                            writer.writerow([
                                element_name, 
                                element_u_value,
                                layer,
                                composition,
                                ratio,
                                name,
                                application,
                                lifetime,
                                thickness
                                ])
                        elif "heterogeneous" in component_classes:
                            layer = component.find_element(By.CSS_SELECTOR, "div.heterogeneous > span.identifier").text
                            
                            sublayers = component.find_elements(By.CSS_SELECTOR, "div.heterogeneous > div.sublayer")
                            for sublayer in sublayers:
                                composition = sublayer.find_element(By.CSS_SELECTOR, "span.identifier").text[:-1]
                                ratio = from_percentage_to_number(sublayer.find_element(By.CSS_SELECTOR, "span.surfaceWeight").text)
                                name = sublayer.find_element(By.CSS_SELECTOR, "span.name").text
                                application = sublayer.find_element(By.CSS_SELECTOR, "span.category").text
                                lifetime = find_number_in_string(sublayer.find_element(By.CSS_SELECTOR, "div.properties > div.lifetime").text)
                                try:
                                    thickness = find_number_in_string(sublayer.find_element(By.CSS_SELECTOR, "div.properties > div.param1").text)
                                except:
                                    # logging.info(f"No thickness found for:\n  element '{element_name}'\n  component '{name}' - '{application}'")
                                    thickness = None

                                writer.writerow([
                                    element_name, 
                                    element_u_value,
                                    layer,
                                    composition,
                                    ratio,
                                    name,
                                    application,
                                    lifetime,
                                    thickness
                                    ])
                        else:
                            raise ValueError(f"Unknown component class: '{component_classes}'")
                    except (NoSuchElementException, TimeoutException) as e:
                        logging.error(f"Failed to scrape component for element '{element_name}': {e}")
                        traceback.print_exc()
            except Exception as e:
                logging.error(f"Error processing element '{element_name}' at {i + 1}: {e}")
                traceback.print_exc()

    logging.info("Finished scraping elements")


def scrape_components():
    components_base_selector = "#app > div.library > div.libraryDetail.COMPONENT > div > div.south-part"
    components_list_selector = f"{components_base_selector} > div.filterAndList > div.listArea > div.listWrapper > div"
    components_selector = f"{components_list_selector} > div"
    selection_details_selector = f"{components_base_selector} > div.selectionDetails"
    
    application_unit_selector = f"{selection_details_selector} > div.epdDetails > div.applicationUnitSelector"
    application_unit_details = f"{selection_details_selector} > div.epdDetails > div.applicationUnitDetails"
    application_unit_type_selectors = {
        'name': f"{application_unit_details} > span.title > span.name",
        'application': f"{application_unit_details} > span.title > span.category",
        'properties': f"{application_unit_details} > div.collapsiblePanel > div.content > div.properties",
        'reversibility_toggle_path': f"{application_unit_details} > div.collapsiblePanel.reversibility",
        'type_of_assembly': f"{application_unit_details} > div.collapsiblePanel.reversibility > div.content > div.typeOfAssembly > div.type > span.value",
        'end_of_life_toggle_path': f"{application_unit_details} > div.collapsiblePanel.endOfLife",
        'materials': f"{application_unit_details} > div.collapsiblePanel.endOfLife > div.content > table > tbody > tr"
    }

    worksection_details_selector = f"{selection_details_selector} > div.worksectionDetails"
    worksection_type_selectors = {
        'name': f"{worksection_details_selector} > span.title > span.name",
        'application': f"{worksection_details_selector} > span.title > span.category",
        'properties': f"{worksection_details_selector} > div > div.collapsiblePanel > div.content > div.properties",
        'reversibility_toggle_path': f"{worksection_details_selector} > div > div.collapsiblePanel.reversibility",
        'type_of_assembly': f"{worksection_details_selector} > div > div.collapsiblePanel.reversibility > div.content > div.typeOfAssembly > div.type > span.value",
        'end_of_life_toggle_path': f"{worksection_details_selector} > div > div.collapsiblePanel.endOfLife",
        'materials': f"{worksection_details_selector} > div > div.collapsiblePanel.endOfLife > div.content > table > tbody > tr"
    }

    worksection_grouped_details_selector = f"{selection_details_selector} > div.groupDetails > div.worksectionDetails"
    worksection_grouped_type_selectors = {
        'name': f"{worksection_grouped_details_selector} > span.title > span.name",
        'application': f"{worksection_grouped_details_selector} > span.title > span.category",
        'properties': f"{worksection_grouped_details_selector} > div > div.collapsiblePanel > div.content > div.properties",
        'reversibility_toggle_path': f"{worksection_grouped_details_selector} > div > div.collapsiblePanel.reversibility",
        'type_of_assembly': f"{worksection_grouped_details_selector} > div > div.collapsiblePanel.reversibility > div.content > div.typeOfAssembly > div.type > span.value",
        'end_of_life_toggle_path': f"{worksection_grouped_details_selector} > div > div.collapsiblePanel.endOfLife",
        'materials': f"{worksection_grouped_details_selector} > div > div.collapsiblePanel.endOfLife > div.content > table > tbody > tr"
    }


    def extract_component_properties(component_detail_selectors):
        properties = {
            'category': None,
            'type': None,
            'database': None,
            'lci_id': None,
            'lambda': None,
            'r_value': None,
            'u_value': None,
            'density': None,
            'functional_unit': None
        }
        property_elements = driver.find_elements(By.CSS_SELECTOR, component_detail_selectors['properties'])
        for property_element in property_elements:
            for sub_element in property_element.find_elements(By.CSS_SELECTOR, "span.property"):
                label_element = sub_element.find_element(By.CSS_SELECTOR, "span.label")
                if not label_element:
                    continue
                label_text = label_element.text.strip()

                if label_text == "Category":
                    properties['category'] = sub_element.find_element(By.CSS_SELECTOR, "span.value").text
                elif label_text == "Type":
                    properties['type'] = sub_element.find_element(By.CSS_SELECTOR, "span.value").text
                elif label_text == "Database":
                    properties['database'] = sub_element.find_element(By.CSS_SELECTOR, "span.value").text
                elif label_text == "ID":
                    properties['lci_id'] = sub_element.find_element(By.CSS_SELECTOR, "span.value").text
                elif label_text == "Lambda":
                    properties['lambda'] = sub_element.find_element(By.CSS_SELECTOR, "span.value").text
                elif label_text == "R-value":
                    properties['r_value'] = sub_element.find_element(By.CSS_SELECTOR, "span.value").text
                elif label_text == "U-value":
                    properties['u_value'] = sub_element.find_element(By.CSS_SELECTOR, "span.value").text
                elif label_text == "Density":
                    properties['density'] = sub_element.find_element(By.CSS_SELECTOR, "span.value").text
                    if properties['density'] in ["Not applicable", "Unknown"]:
                        properties['density'] = None
                elif label_text == "Functional unit":
                    properties['functional_unit'] = sub_element.find_element(By.CSS_SELECTOR, "span.value").text
        return properties
    
    def extract_component_type_of_assembly(component_identifier, detail_selectors):
        has_reversibility = len(driver.find_elements(By.CSS_SELECTOR, detail_selectors['reversibility_toggle_path'])) == 1
        if not has_reversibility:
            logging.info(f"Reversibility toggle not found for '{component_identifier}'")
            return None

        is_reversibility_open = len(driver.find_elements(By.CSS_SELECTOR, f"{detail_selectors['reversibility_toggle_path']} > div.headerWrapper > span.button.open")) == 1
        if not is_reversibility_open:
            reversibility_toggle = driver.find_element(By.CSS_SELECTOR, f"{detail_selectors['reversibility_toggle_path']} > div.headerWrapper > span.header")
            safe_click(reversibility_toggle)
            wait_for_element(f"{detail_selectors['reversibility_toggle_path']} > div.headerWrapper > span.button.open")

        type_of_assembly = driver.find_elements(By.CSS_SELECTOR, detail_selectors['type_of_assembly'])
        if len(type_of_assembly) != 1:
            logging.info(f"Type of assembly not found for '{component_identifier}'")
            return None
        
        return type_of_assembly[0].text
    
    def extract_component_materials(component_identifier, detail_selectors):
        material_data = []

        has_end_of_life = len(driver.find_elements(By.CSS_SELECTOR, detail_selectors['end_of_life_toggle_path'])) == 1
        if not has_end_of_life:
            logging.info(f"End of life toggle not found for '{component_identifier}'")
            return material_data

        is_end_of_life_open = len(driver.find_elements(By.CSS_SELECTOR, f"{detail_selectors['end_of_life_toggle_path']} > div.headerWrapper > span.button.open")) == 1
        if not is_end_of_life_open:
            end_of_life_toggle = driver.find_element(By.CSS_SELECTOR, f"{detail_selectors['end_of_life_toggle_path']} > div.headerWrapper > span.header")
            safe_click(end_of_life_toggle)
            wait_for_element(f"{detail_selectors['end_of_life_toggle_path']} > div.headerWrapper > span.button.open")
        
        materials = driver.find_elements(By.CSS_SELECTOR, detail_selectors['materials'])
        if len(materials) == 0:
            logging.info(f"No materials found for '{component_identifier}'")
            return material_data
        
        for material in materials:
            material_data.append({
                'description': material.find_element(By.CSS_SELECTOR, "td.description").text,
                'waste_category': material.find_element(By.CSS_SELECTOR, "td.wsn").text,
                'landfill': material.find_element(By.CSS_SELECTOR, "td.landfill").text,
                'incineration': material.find_element(By.CSS_SELECTOR, "td.incineration").text,
                'reuse': material.find_element(By.CSS_SELECTOR, "td.reuse").text,
                'recycling': material.find_element(By.CSS_SELECTOR, "td.recycling").text,
                'sorted_on_site': material.find_element(By.CSS_SELECTOR, "td.sorted").text
            })
        return material_data

    def scrape_component(detail_selectors):
        component_name = wait_for_element(detail_selectors['name']).text                
        component_application = wait_for_element(detail_selectors['application']).text
        component_identifier = f"'{component_name}' - '{component_application}'"
        properties = extract_component_properties(detail_selectors)
        type_of_assembly = extract_component_type_of_assembly(component_identifier, detail_selectors)
        materials = extract_component_materials(component_identifier, detail_selectors)

        for material in materials:
            min_density, max_density = find_min_max_number_in_string(properties['density']) if properties['density'] else (None, None)
            writer.writerow([
                component_name,
                component_application,
                properties['category'],
                properties['type'],
                properties['database'],
                properties['lci_id'],
                find_number_in_string(properties['lambda']) if properties['lambda'] else None,
                find_number_in_string(properties['r_value']) if properties['r_value'] else None,
                find_number_in_string(properties['u_value']) if properties['u_value'] else None,
                min_density,
                max_density,
                format_functional_unit(properties['functional_unit']),
                type_of_assembly,
                material['description'],
                material['waste_category'],
                from_percentage_to_number(material['landfill']),
                from_percentage_to_number(material['incineration']),
                from_percentage_to_number(material['reuse']),
                from_percentage_to_number(material['recycling']),
                from_percentage_to_number(material['sorted_on_site']) if "%" in material['sorted_on_site'] else material['sorted_on_site']
            ])

    logging.info("Scraping components...")
    driver.get("https://www.totem-building.be/user.library.xhtml?l=COMPONENT")
    wait_for_element(application_unit_details)

    components_list = driver.find_element(By.CSS_SELECTOR, components_list_selector)
    components = driver.find_elements(By.CSS_SELECTOR, components_selector)

    logging.info(driver.find_element(By.CSS_SELECTOR, f"{components_base_selector} > div.filterAndList > div.listArea > div.listAreaTitle > span.totalSize").text)
    logging.info(f"Elements in list: {len(components)}")

    counter = 0
    with open('components.csv', mode='w', newline='') as file:
        writer = csv.writer(file, delimiter=';')
        writer.writerow(['Component Name', 'Application', 'Category', 'Type', 
                         'Database', 'LCI-ID', 'Lambda', 'R-Value', 'U-Value', 'Min Density', 'Max Density',
                         'Functional Unit', 'Type of Assembly', 'Material', 'Waste Category', 'Landfill', 
                         'Incineration', 'Reuse', 'Recycling', 'Sorted on Building Site'])

        for i in range(len(components)):
            try:
                # Re-fetch to avoid StaleElementReferenceException
                components = driver.find_elements(By.CSS_SELECTOR, components_selector)
                component = components[i]

                # Update component details
                safe_click(component)
                scroll_to_element(components_list, component)

                # Scrape
                selection_detail = driver.find_element(By.CSS_SELECTOR, f"{selection_details_selector} > div")
                selection_detail_classes = selection_detail.get_attribute("class")

                if "epdDetails" in selection_detail_classes:
                    application_unit_selectors = driver.find_elements(By.CSS_SELECTOR, application_unit_selector)
                    if len(application_unit_selectors) == 1:
                        tabs = application_unit_selectors[0].find_elements(By.CSS_SELECTOR, "div.tab")[1:]
                        for tab in tabs:
                            safe_click(tab)
                            scrape_component(application_unit_type_selectors)
                            counter += 1
                    else:
                        scrape_component(application_unit_type_selectors)
                        counter += 1
                elif "worksectionDetails" in selection_detail_classes:
                    scrape_component(worksection_type_selectors)
                    counter += 1
                elif "groupDetails" in selection_detail_classes:
                    tabs = selection_detail.find_elements(By.CSS_SELECTOR, f"div.variantSelector > div.tab")[1:]
                    for tab in tabs:
                        safe_click(tab)
                        scrape_component(worksection_grouped_type_selectors)
                        counter += 1
                else:
                    logging.error(selection_detail.get_attribute("outerHTML"))
                    raise ValueError(f"Unknown selection detail class: '{selection_detail_classes}'")
            except Exception as e:
                try:
                    component_name = "Unknown"
                    component_application = "Unknown"

                    detail_selectors = [application_unit_type_selectors, worksection_type_selectors]
                    for detail_selector in detail_selectors:
                        try:
                            component_name = driver.find_element(By.CSS_SELECTOR, detail_selector['name']).text
                            component_application = driver.find_element(By.CSS_SELECTOR, detail_selector['application']).text
                            break
                        except:
                            pass
                except:
                    pass
                logging.error(f"Error processing component '{component_name}' - '{component_application}': {e}")
                traceback.print_exc()
        
    logging.info(f"Finished scraping {counter} components")

def main():
    try:
        login()
        scrape_elements()
        scrape_components()
    except Exception as e:
        logging.error(f"Fatal error occurred: {e}")
        traceback.print_exc()
    finally:
        logging.info("Closing the driver")
        driver.quit()

if __name__ == '__main__':
    main()