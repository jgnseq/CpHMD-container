/*

  TO COMPILE:
    gcc fixgro.c -o fixgro -O3 -lm -Wall -W -pedantic -Wno-unused-result
    gcc fixgro.c -o fixgro -O3 -lm -Wall -W -pedantic -ansi


  TODO:

  - Maybe make stages into a structure array (like atom[], mol[],
    group[]) with a typedef, including the group number as a structure
    variable, making the 2nd reading of A-lines unnecessary.

  - Maybe collect box-related variables into a structure.

  - Improve clustering algorithm: It is currently O(N^3) but could
    probably become O(N^2). See comments before assemble_objs() and
    SLINK-docs directory.

*/

// Some of these includes may not be needed.........
#include <stdio.h>
#include <stdlib.h>
//#include <unistd.h>
#include <string.h>
#include <errno.h>
#include <stdarg.h>
#include <math.h>

#define MAXSTR 200
#define BIG_DISTANCE 1e20

typedef struct {
  int anumb, rnumb, mol ;
  float r[3], s[3] ;
  char aname[6+1], rname[6+1], vels[24+1] ;
} atom_t ;

typedef struct {
  int nmols, *mol ;
  char name[MAXSTR] ;
} group_t ;

typedef struct {
  int firstatom, lastatom ;
} mol_t ;

typedef struct {
  float dRMI2, dS[3] ;
} dist_t ;

typedef struct {
  int mol, dn[3], assembled ;
} obj_t ;


/* Function prototypes */
void parse_arguments(int argc, char **argv) ;
void read_frame(void) ;
void read_moldef(void) ;
void write_frame(void) ;
int gnumb(char groupname[]) ;
void r_to_s(void) ;
void s_to_r(void) ;
void compute_objdist(void) ;
void assemble_objs(void) ;
void center(void) ;
void apply_PBCs(void) ;
int nint(float x) ;
void message(char mtype, char *format, ...) ;

/* Global variables */
int natoms, ngroups, nmols, nstages, *nobjs, nobjs_tot,
  gcent[3], usePBC[3], nframe = 0 ;
float H[3][3], iH[3][3], boxC[3] ;  // maybe collect into a box structure
char title[MAXSTR+1], boxline[MAXSTR+1] ;
atom_t *atom ;
group_t *group ;
mol_t *mol ;
dist_t **dist ;
obj_t *obj ;
FILE *fp_gro, *fp_moldef ;


int main(int argc, char **argv)
{
  parse_arguments(argc, argv) ;

  while (fgets(title, sizeof title, fp_gro) != NULL)
  {
    nframe++ ;
    read_frame() ;
    if(nframe == 1) read_moldef() ;
    r_to_s() ;
    compute_objdist() ;
    assemble_objs() ;
    center() ;
    apply_PBCs() ;
    s_to_r() ;
    write_frame() ;
  }
  fclose(fp_gro) ;

  // free stuff...

  return 0 ;
}


/*Reads arguments*/
void parse_arguments(int argc, char **argv)
{
  char *gro_file, *moldef_file ;

  if (argc != 3) message('U', "Wrong number of arguments.\n") ;

  gro_file = calloc(strlen(argv[1])+1, sizeof(char)) ;
  strcpy(gro_file, argv[1]) ;
  if ((fp_gro = fopen(gro_file, "r")) == NULL)
    message('E', "Opening \"%s\": %s\n", gro_file, strerror(errno));

  moldef_file = calloc(strlen(argv[2])+1, sizeof(char)) ;
  strcpy(moldef_file, argv[2]) ;
  if ((fp_moldef = fopen(moldef_file, "r")) == NULL)
    message('E', "Opening \"%s\": %s\n", moldef_file, strerror(errno));
}


void read_frame(void)
{
  int a, k ;
  char line[MAXSTR+1], resname[6], atmname[6] ;

  //fgets(title, sizeof title, fp_gro) ;

  fgets(line, sizeof line, fp_gro) ;
  sscanf(line, "%d", &natoms) ;
  atom = calloc(natoms+1, sizeof(atom_t)) ;

  // Read atoms:
  for (a = 1 ; a <= natoms ; a++)
  {
    fgets(line, sizeof line, fp_gro) ;
    sscanf(line, "%5d%5[^\n]%5[^\n]%5d%8f%8f%8f%24[^\n]",
	   &(atom[a].rnumb), resname, atmname, &(atom[a].anumb),
	   &(atom[a].r[0]), &(atom[a].r[1]), &(atom[a].r[2]), atom[a].vels) ;
    sscanf(resname, "%s", atom[a].rname) ;
    sscanf(atmname, "%s", atom[a].aname) ;
  }
  fgets(boxline, sizeof boxline, fp_gro) ;
  sscanf(boxline, "%f %f %f %f %f %f %f %f %f",
	 &(H[0][0]), &(H[1][1]), &(H[2][2]), &(H[1][0]), &(H[2][0]),
	 &(H[0][1]), &(H[2][1]), &(H[0][2]), &(H[1][2])) ;
  //fclose(fp_gro) ;

  // Compute inverse of H:
  // (Derived with Maxima assuming ay=az=bz=0, as used by GROMACS; see
  // manual-2016.1.pdf, sec. 3.2. Perhaps made fully general.)
  iH[0][0] = 1/H[0][0] ;
  iH[0][1] = -H[0][1] / (H[0][0]*H[1][1]) ;
  iH[0][2] = (H[0][1]*H[1][2]-H[1][1]*H[0][2]) / (H[0][0]*H[1][1]*H[2][2]) ;
  iH[1][0] = 0 ;
  iH[1][1] = 1/H[1][1] ;
  iH[1][2] = -H[1][2] / (H[1][1]*H[2][2]) ;
  iH[2][0] = 0 ;
  iH[2][1] = 0 ;
  iH[2][2] = 1/H[2][2] ;

  // Compute box center:
  for(k = 0 ; k < 3 ; k++)
    boxC[k] = (H[k][0] + H[k][1] + H[k][2]) / 2 ;
}


// Strictly speaking, all calloc() calls should be followed by
// assignment of its variables, because zero-bytes do not necessarily
// correspond to zero integers or floats, or even to NULL pointers;
// thus, calloc() is really not much different from malloc() in this
// respect. However, this is perhaps a bit paranoid, since virtually
// all existing compilers actually do that...

// Consider using fseek() instead of rewind().

void read_moldef(void)
{
  // Try to simplify/reduce the number of auxiliary variables...
  int k, g, a, m, gm, prevrnumb, i, subg, st, gst, notot, o ;
  char line[MAXSTR+1], auxname[MAXSTR], auxstr[3][MAXSTR] ;

  // 1st pass: count groups and assembly stages
  ngroups = nstages = 0 ;
  while(fgets(line, sizeof line, fp_moldef) != NULL)
  {
    if (line[0] == 'G') ngroups++ ;
    else if (line[0] == 'A') nstages++ ;
  }
  group = calloc(ngroups+1, sizeof(group_t)) ;
  nobjs = calloc(nstages+1, sizeof(int)) ;  // indices 0 through nstages are used

  // 2nd pass: read group names, count total and per-group molecules
  rewind(fp_moldef) ;
  g = 0 ;
  nmols = 0 ;
  prevrnumb = 0 ;
  st = 0 ;
  nobjs_tot = 0 ;
  while(fgets(line, sizeof line, fp_moldef) != NULL)
  {
    if (line[0] == 'G')
      sscanf(line, "G %s", group[++g].name) ;
    else if (line[0] == 'a')
    {
      group[g].nmols++ ;
      nmols++ ;
    }
    else if (line[0] == 'n')
    {
      sscanf(line, "n %s", auxname) ;
      for (a = 1 ; a <= natoms ; a++)
      {
	if (strcmp(auxname, atom[a].rname) == 0)
	{
	  if (atom[a].rnumb != prevrnumb)
	  {
	    group[g].nmols++ ;
	    nmols++ ;
	  }
	}
	prevrnumb = atom[a].rnumb ;
      }
    }
    else if (line[0] == 'g')
    {
      sscanf(line, "g %s", auxname) ;
      group[g].nmols += group[gnumb(auxname)].nmols ;
      //subg = gnumb(auxname) ;
      //group[g].nmols += group[subg].nmols ;
    }
    else if (line[0] == 'A')
    {
      sscanf(line, "A %s", auxname) ;
      nobjs[++st] = nobjs_tot += group[gnumb(auxname)].nmols ;
      //gst = gnumb(auxname) ;
      //nobjs[++st] = nobjs_tot += group[gst].nmols ;
    }
  }
  mol = calloc(nmols+1, sizeof(mol_t)) ;
  for (g = 1 ; g <= ngroups ; g++)
    group[g].mol = calloc(group[g].nmols+1, sizeof(int)) ;
  obj = calloc(nobjs_tot+1, sizeof(obj_t)) ;
  dist = calloc(nobjs_tot+1, sizeof(dist_t *)) ;
  for (o = 1 ; o <= nobjs_tot ; o++)
    dist[o] = calloc(nobjs_tot+1, sizeof(dist_t)) ;

  // 3rd pass: assign molecules to groups and atoms to molecules.
  rewind(fp_moldef) ;
  g = m = gm = 0 ;
  prevrnumb = 0 ;
  notot = 0 ;
  while(fgets(line, sizeof line, fp_moldef) != NULL)
  {
    if (line[0] == 'G')
    {
      g++ ;
      gm = 0 ;
    }
    else if (line[0] == 'a')
    {
      group[g].mol[++gm] = ++m ;
      sscanf(line, "a %d %d", &(mol[m].firstatom), &(mol[m].lastatom)) ;
      for (a = mol[m].firstatom ; a <= mol[m].lastatom ; a++)
      {
	if (atom[a].mol == 0) atom[a].mol = m ;
	else message('E', "Atom index %d already assigned to molecule.", a) ;
      }
    }
    else if (line[0] == 'n')
    {
      sscanf(line, "n %s", auxname) ;
      for (a = 1 ; a <= natoms ; a++)
      {
	if (strcmp(auxname, atom[a].rname) == 0)
	{
	  if (atom[a].rnumb != prevrnumb) group[g].mol[++gm] = ++m ;
	  if (mol[m].firstatom == 0) mol[m].firstatom = a ;
	  mol[m].lastatom = a ;
	  if (atom[a].mol == 0) atom[a].mol = m ;
	  else message('E', "Atom %d already assigned to molecule.",
		       atom[a].anumb) ;
	}
	prevrnumb = atom[a].rnumb ;
      }
    }
    else if (line[0] == 'g')
    {
      sscanf(line, "g %s", auxname) ;
      subg = gnumb(auxname) ;
      for (i = 1 ; i <= group[subg].nmols ; i++)
	group[g].mol[++gm] = group[subg].mol[i] ;
    }
    else if (line[0] == 'A')
    {
      sscanf(line, "A %s", auxname) ;
      gst = gnumb(auxname) ;
      for (i = 1 ; i <= group[gst].nmols ; i++)
	obj[++notot].mol = group[gst].mol[i] ;
    }
    else if (line[0] == 'C')
    {
      sscanf(line, "C %s %s %s", auxstr[0], auxstr[1], auxstr[2]) ;
      for (k = 0 ; k < 3 ; k++)	gcent[k] = gnumb(auxstr[k]) ;
    }
    else if (line[0] == 'P')
    {
      sscanf(line, "P %d %d %d", &(usePBC[0]), &(usePBC[1]), &(usePBC[2])) ;
      for (k = 0 ; k < 3 ; k++)
	if (usePBC[k] != 0 && usePBC[k] != 1)
	  message('E', "Use PBC = 0 or 1.") ;
    }

  }

//  // Check if everything was properly read:
//  fprintf(stderr, "%d %d %d\n", ngroups, nmols, natoms) ;
//  for (g = 1 ; g <= ngroups ; g++)
//  {
//    fprintf(stderr, "%s  %d\n", group[g].name, group[g].nmols) ;
//    for (i = 1 ; i <= group[g].nmols ; i++)
//    {
//      m = group[g].mol[i] ;
//      fprintf(stderr, "  %6d  %6d\n", mol[m].firstatom, mol[m].lastatom) ;
//    }
//  }
//  for (st = 1 ; st <= nstages ; st++)
//  {
//    fprintf(stderr, "O  %d\n", st) ;
//    for (o = nobjs[st-1]+1 ; o <= nobjs[st] ; o++)
//      fprintf(stderr, "O      %d\n", obj[o].mol) ;
//  }
//  fprintf(stderr, "C %d %d %d\n", gcent[0], gcent[1], gcent[2]) ;
//  fprintf(stderr, "P %d %d %d\n", usePBC[0], usePBC[1], usePBC[2]) ;

  // Some final checks:
  for (g = 1 ; g <= ngroups ; g++)
    if (group[g].nmols == 0)
      message('E', "Group %d (%s) is empty.\n", g, group[g].name) ;
  for (a = 1 ; a <= natoms ; a++)
    if (atom[a].mol == 0)
      message('E', "Atom %d not assigned to a molecule.\n", a) ;

  fclose(fp_moldef) ;
}


void write_frame(void)
{
  int a ;

  printf("%s", title) ;  // already '\n'-terminated
  printf("%d\n", natoms) ;
  for (a = 1 ; a <= natoms ; a++)
  {
    printf("%5d%-5s%5s%5d%8.3f%8.3f%8.3f%s\n",
	   atom[a].rnumb, atom[a].rname, atom[a].aname, atom[a].anumb,
	   atom[a].r[0], atom[a].r[1], atom[a].r[2], atom[a].vels) ;
  }
  printf("%s", boxline) ;  // already '\n'-terminated
//  printf(" %9.5f %9.5f %9.5f %9.5f %9.5f %9.5f %9.5f %9.5f %9.5f\n",
//	 H[0][0], H[1][1], H[2][2], H[1][0], H[2][0],
//	 H[0][1], H[2][1], H[0][2], H[1][2]) ;
}


int gnumb(char groupname[])
{
  int g, gg = -1 ;

  for (g = 1 ; g <= ngroups ; g++)
    if (strcmp(groupname, group[g].name) == 0) gg = g ;
  if (gg == -1) message('E', "Group %s not defined.", groupname) ;
  return gg ;
}


void r_to_s(void)
{
  int a, k, j ;

  for (a = 1 ; a <= natoms ; a++)
    for (k = 0 ; k < 3 ; k++)
    {
      atom[a].s[k] = 0 ;
      for (j = 0 ; j < 3 ; j++)
	atom[a].s[k] += iH[k][j]*(atom[a].r[j]-boxC[j]) ;
    }
}

void s_to_r(void)
{
  int a, k, j ;

  for (a = 1 ; a <= natoms ; a++)
    for (k = 0 ; k < 3 ; k++)
    {
      atom[a].r[k] = boxC[k] ;
      for (j = 0 ; j < 3 ; j++)
	atom[a].r[k] += H[k][j]*atom[a].s[j] ;
    }
}


// Compute inter-molecular distances as the one between their closest atoms.
void compute_objdist(void)
{
  int o1, o2, m1, m2, a1, a2, k, j ;
  float d2_min, drMI2, ds[3] = {0,0,0}, dsMI[3] = {0,0,0}, drMI[3] = {0,0,0} ;

  for (o1 = 1 ; o1 < nobjs_tot ; o1++)
  for (o2 = o1+1 ; o2 <= nobjs_tot ; o2++)
  {
    d2_min = BIG_DISTANCE ;
    m1 = obj[o1].mol ;
    m2 = obj[o2].mol ;
    for (a1 = mol[m1].firstatom ; a1 <= mol[m1].lastatom ; a1++)
    for (a2 = mol[m2].firstatom ; a2 <= mol[m2].lastatom ; a2++)
    {
      drMI2 = 0 ;
      for (k = 0 ; k < 3 ; k++)
      {
	ds[k] = atom[a2].s[k] - atom[a1].s[k] ;
	dsMI[k] = ds[k] - nint(ds[k]) ;
	drMI[k] = 0 ;
	for (j = 0 ; j < 3 ; j++) drMI[k] += H[k][j] * dsMI[j] ;
	drMI2 += drMI[k] * drMI[k] ;
      }
      if (drMI2 < d2_min)
      {
	dist[o1][o2].dRMI2 = dist[o2][o1].dRMI2 = d2_min = drMI2 ;
	for (k = 0 ; k < 3 ; k++)
	{
	  dist[o1][o2].dS[k] = ds[k] ;
	  dist[o2][o1].dS[k] = -ds[k] ;
	}
      }
    }
  }
}


// This algorithm scales with the cube of the number of objects, but
// one scaling with the square (e.g., based on clever distance
// sorting) can probably be devised.
void assemble_objs(void)
{
  int st, not_empty, o1, o2, o1_min = -1, o2_min = -1, a, k, m ;
  float d2_min ;

  for (o1 = 1 ; o1 <= nobjs_tot ; o1++) obj[o1].assembled = 0 ;

  // Use first object as nucleation point:
  obj[1].assembled = 1 ;
  for (k = 0 ; k < 3 ; k++) obj[1].dn[k] = 0 ;

  // Cluster objects by sequential assembling stages:
  for (st = 1 ; st <= nstages ; st++)
  {
    do
    {
      d2_min = BIG_DISTANCE ;
      not_empty = 0 ;
      for (o1 = nobjs[st-1]+1 ; o1 <= nobjs[st] ; o1++)
      {
	if (obj[o1].assembled == 0)
	{
	  not_empty = 1 ;
	  for (o2 = 1 ; o2 <= nobjs[st] ; o2++)
	  {
	    // ToDo: try to switch the two conditions and use fastest order.
	    if (obj[o2].assembled == 1)
	    {
	      if (dist[o1][o2].dRMI2 < d2_min)
	      {
		d2_min = dist[o1][o2].dRMI2 ;
		o1_min = o1 ;
		o2_min = o2 ;
	      }
	    }
	  }
	}
      }
      if (o1_min != -1 && o2_min != -1)
      {
	obj[o1_min].assembled = 1 ;
	for (k = 0 ; k < 3 ; k++)
	  // Since o2 is already assembled, its dn was already assigned.
	  obj[o1_min].dn[k] = obj[o2_min].dn[k] + nint(dist[o1_min][o2_min].dS[k]) ;
      }
    }
    while (not_empty) ;
  }

  // Apply box displacements from assembling:
  for (o1 = 1 ; o1 <= nobjs_tot ; o1++)
  {
    m = obj[o1].mol ;
    for (a = mol[m].firstatom ; a <= mol[m].lastatom ; a++)
      for(k = 0 ; k < 3 ; k++) atom[a].s[k] += obj[o1].dn[k] ;
  }
}


void center(void)
{
  int k, g, i, m, a ;
  float smin[3], smax[3], smid ;

  for (k = 0 ; k < 3 ; k++)
  {
    smin[k] = +BIG_DISTANCE ;
    smax[k] = -BIG_DISTANCE ;
    g = gcent[k] ;
    for (i = 1 ; i <= group[g].nmols ; i++)
    {
      m = group[g].mol[i] ;
      for (a = mol[m].firstatom ; a <= mol[m].lastatom ; a++)
      {
	if (atom[a].s[k] < smin[k]) smin[k] = atom[a].s[k] ;
	if (atom[a].s[k] > smax[k]) smax[k] = atom[a].s[k] ;
      }
    }
    smid = 0.5 * (smin[k] + smax[k]) ;
    for (a = 1 ; a <= natoms ; a++) atom[a].s[k] -= smid ;
    // Check if box ranges were exceeded:
    if (smax[k] - smin[k] > 1)
    {
      message((usePBC[k] ? 'E' : 'W'),
	      "Range of box vector %d exceeded by %s in frame %d.\n",
	      k, group[gcent[k]].name, nframe) ;
    }
  }
}


void apply_PBCs(void)
{
  int k, m, a, dN ;
  float sCOM ;

  for(k = 0 ; k < 3 ; k++)
  {
    if (usePBC[k] == 1)
      for (m = 1 ; m <= nmols ; m++)
      {
	// Compute k-coordinate of m's "COM" (actually, geometric center):
	sCOM = 0 ;
	for (a = mol[m].firstatom ; a <= mol[m].lastatom ; a++)
	  sCOM += atom[a].s[k] ;
	sCOM /= (mol[m].lastatom - mol[m].firstatom + 1) ;
	// Move m's atoms to inside the reference box:
	dN = nint(sCOM) ;
	for (a = mol[m].firstatom ; a <= mol[m].lastatom ; a++)
	  atom[a].s[k] -= dN ;
      }
  }
}


// Fortran-like named. Useful property: nint(-x) = -nint(x)
int nint(float x)
{
  return floor(x + 0.5) ;
}


void message(char mtype, char *format, ...)
{
  va_list args ;
  const char cmd[] = "fixgro" ;
  const char usage[] = "Usage: %s GRO_FILE MOLDEF_FILE\n" ;

  va_start(args, format) ;
  if (mtype != 'W' && mtype != 'E' && mtype != 'U')
    message('E', "Wrong use of message() function.\n") ;
  if (mtype == 'W') fprintf(stderr, "%s: WARNING: ", cmd) ;
  else fprintf(stderr, "%s: ERROR: ", cmd) ;
  vfprintf(stderr, format, args) ;
  va_end(args) ;
  if (mtype == 'U') fprintf(stderr, usage, cmd) ;
  if (mtype != 'W') exit(1) ;
}
