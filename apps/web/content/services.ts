import { images } from "./images";

export type MarketingService = {
  slug: string; name: string; description: string; promise: string; image: { src: string; alt: string };
  bookingServiceId?: string; problems: string[]; included: string[]; preparation: string;
};

const common = {
  included: ["A clear assessment of the requested work", "Professional care for your home and work area", "A tidy handover and clear next steps"],
  preparation: "Keep the work area accessible and share any useful access or safety details during booking.",
};

export const marketingServices: MarketingService[] = [
  { slug:"plumbing", name:"Plumbing", description:"Help with leaks, fixtures, drains and everyday plumbing faults.", promise:"Stop small plumbing problems becoming big ones.", image:images.plumbing, bookingServiceId:"plumbing", problems:["Leaking taps or pipework","Slow or blocked drains","Faulty fixtures and toilets"], ...common },
  { slug:"electrical", name:"Electrical", description:"Qualified help with outlets, switches, lighting and troubleshooting.", promise:"Safe, careful help for the electrical jobs around your home.", image:images.electrical, bookingServiceId:"electrical", problems:["Outlets or switches not working","Lighting faults","Electrical troubleshooting"], ...common },
  { slug:"handyman", name:"Handyman", description:"Practical help with mounting, assembly, repairs and home projects.", promise:"Get the list done properly.", image:images.handyman, bookingServiceId:"handyman", problems:["Furniture assembly","Shelving and mounting","Minor repairs"], ...common },
  { slug:"heating", name:"Heating", description:"Heating checks, troubleshooting and maintenance information.", promise:"Keep your home comfortable when it matters.", image:images.heating, problems:["Uneven heat","Heating controls","Maintenance questions"], ...common },
  { slug:"cooling", name:"Cooling", description:"Cooling-system checks and household comfort support.", promise:"A calmer way to keep your home cool.", image:images.cooling, problems:["Poor cooling performance","Controls and airflow","Seasonal maintenance"], ...common },
  { slug:"appliance-repair", name:"Appliance repair", description:"Diagnosis and repair for common household appliances.", promise:"Give essential appliances a practical path back to working order.", image:images.applianceRepair, bookingServiceId:"appliance", problems:["Appliance not starting","Unusual noise or behaviour","Performance problems"], ...common },
  { slug:"cleaning", name:"Cleaning", description:"Reliable, detail-focused home cleaning shaped around your needs.", promise:"Come home to a space that feels cared for.", image:images.cleaning, bookingServiceId:"cleaning", problems:["Regular home cleaning","Deep-clean priorities","Move-in or move-out cleaning"], ...common },
  { slug:"locksmith", name:"Locksmith", description:"Information and help finding appropriate support for locks and access.", promise:"Clear next steps when access cannot wait.", image:images.locksmith, problems:["Lock faults","Lost-key guidance","Door security questions"], ...common },
  { slug:"painting", name:"Painting", description:"Careful preparation and painting support for everyday rooms.", promise:"A cleaner route to a fresh-looking home.", image:images.painting, problems:["Room refreshes","Preparation and patching","Trim and detail work"], ...common },
  { slug:"carpentry", name:"Carpentry", description:"Practical support for woodwork, fittings and smaller home projects.", promise:"Skilled help for the details that make a home work.", image:images.carpentry, problems:["Door and trim adjustments","Shelving and fittings","Minor wood repairs"], ...common },
  { slug:"moving-help", name:"Moving help", description:"Extra hands and practical support for moving day.", promise:"Make moving day feel more manageable.", image:images.movingHelp, problems:["Lifting and moving","Furniture setup","Move-in practical tasks"], ...common },
  { slug:"home-maintenance", name:"Home maintenance", description:"Planned help with the small jobs that keep your home in shape.", promise:"Stay ahead of the household to-do list.", image:images.homeMaintenance, problems:["Seasonal checks","Preventive maintenance","A mixed list of small jobs"], ...common },
];

export const marketingServiceBySlug = (slug: string) => marketingServices.find((service) => service.slug === slug);

// Intake choices are independent from publication of dedicated marketing pages.
// Every entry is also seeded by the API.
export const intakeServices = [
  { slug: "plumbing", name: "Plumbing" },
  { slug: "electrical", name: "Electrical" },
  { slug: "heating", name: "Heating" },
  { slug: "cooling", name: "Cooling & air conditioning" },
  { slug: "appliance-repair", name: "Appliance repair" },
  { slug: "handyman", name: "Handyman & small repairs" },
  { slug: "home-maintenance", name: "Home maintenance" },
  { slug: "cleaning", name: "Home cleaning" },
  { slug: "locksmith", name: "Locksmith" },
  { slug: "painting", name: "Painting" },
  { slug: "carpentry", name: "Carpentry" },
  { slug: "flooring", name: "Flooring" },
  { slug: "roofing", name: "Roofing" },
  { slug: "gutters", name: "Gutter cleaning & repair" },
  { slug: "windows-doors", name: "Windows & doors" },
  { slug: "garage-door", name: "Garage door service" },
  { slug: "pest-control", name: "Pest control" },
  { slug: "lawn-landscaping", name: "Lawn & landscaping" },
  { slug: "pressure-washing", name: "Pressure washing" },
  { slug: "moving-help", name: "Moving help" },
] as const;
