package test.domain.PO;

import lombok.Data;
import org.neo4j.ogm.annotation.NodeEntity;
import org.neo4j.ogm.annotation.Property;

@Data
@NodeEntity
public class REVIEWED extends BaseRelationShip {
    @Property(name = "rating")
    private Long rating;

    @Property(name = "summary")
    private String summary;
}
